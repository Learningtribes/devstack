"""Real routed search against isolated ES index and rollback-only SQL fixtures."""
import copy
import json
import secrets
import uuid
from datetime import timedelta
import django
from django.conf import settings
from django.db import transaction
from django.test import Client, override_settings
from django.utils import timezone

django.setup()
from django.contrib.auth import get_user_model
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from student.models import CourseAccessRole, UserProfile
from course.models import PrivilegeFlag, UserPrivilegeFlag, CoursePrivilegeFlag
from lms.djangoapps.program_enrollments.models import ProgramAccessRole
from lms.djangoapps.program_enrollments.program_team_roles import ProgramStaffRoles
from search.elastic import ElasticSearchEngine

suffix = secrets.token_hex(5)
prefix = 'py313_search_matrix_' + suffix + '_'
print('isolated_index_prefix', prefix)
system = 'cms' if 'cms' in settings.ROOT_URLCONF else 'lms'
assert settings.FEATURES['ENABLE_COURSEWARE_SEARCH'], 'Search must be enabled in registered settings'
with override_settings(ELASTIC_SEARCH_INDEX_PREFIX=prefix):
    engine = ElasticSearchEngine('courses')
    with transaction.atomic():
        base = CourseOverview.objects.first()
        keys = []
        docs = []
        for index, org in enumerate(('PY313', 'PY313', 'OTHERORG')):
            key = CourseKey.from_string(f'course-v1:{org}+Search{suffix}{index}+2026')
            keys.append(str(key))
            row = copy.deepcopy(base)
            row.pk = key
            row._state.adding = True
            row.org = org
            row.display_name = 'SearchMatrix ' + org
            row.course_status = 'released'
            row.catalog_visibility = 'both'
            row.start = timezone.now() - timedelta(days=1)
            row.save(force_insert=True)
            docs.append(dict(id=str(key),course=str(key),org=org,creator_id=10,
                number=key.course,raw_display_name='SearchMatrix '+org,
                start=row.start.isoformat(),enrollment_start=row.start.isoformat(),
                course_status='released',catalog_visibility='both',languages=['en'],
                content={'display_name':'SearchMatrix '+org}))
        engine.index('course_info',docs,refresh=True)
        password = secrets.token_urlsafe(32)
        users = {}
        for label, is_staff, is_superuser in [('edx',True,True),('py313_staff',True,False),('py313_learner',False,False),('py313_flag',True,False)]:
            user = get_user_model().objects.create_user(username=label+suffix,email=label+suffix+'@example.test',password=password,is_staff=is_staff,is_superuser=is_superuser)
            UserProfile.objects.create(user=user,name='Search role matrix')
            users[label] = user
        staff = users['py313_staff']
        CourseAccessRole.objects.create(user=staff,course_id=keys[0],org='PY313',role='staff')
        flag = PrivilegeFlag.objects.create(name='Search '+suffix)
        UserPrivilegeFlag.objects.create(user=users['py313_flag'],privilege_flag=flag)
        CoursePrivilegeFlag.objects.create(course_id=keys[1],privilege_flag=flag)
        program_ids = [str(uuid.uuid4()) for _ in keys]
        if system == 'cms':
            program_engine = ElasticSearchEngine('programs')
            program_engine.index('program', [dict(id=pid,uuid=pid,org=doc['org'],title='SearchMatrix '+str(i),raw_title='SearchMatrix '+str(i),creator_id=10,start=doc['start'],status='active',languages=['en'],content={'title':'SearchMatrix '+str(i)}) for i,(pid,doc) in enumerate(zip(program_ids,docs))],refresh=True)
            ProgramAccessRole.objects.create(user=staff,program_id=program_ids[0],role=ProgramStaffRoles.ROLE)
        for username in ('edx','py313_staff','py313_flag','py313_learner',None):
            client = Client(HTTP_HOST='localhost:18010' if system == 'cms' else 'localhost:18000')
            if username:
                r = client.post('/login_ajax', {'email':users[username].email,'password':password})
                assert r.status_code == 200 and r.json().get('success'), ('login',username,r.status_code)
            routes = [('/api/courses/v1/courses/', 'get', {'search_term':'SearchMatrix'})]
            if system == 'cms':
                routes.append(('/course_search/', 'post', {'search_string':'SearchMatrix'}))
                routes.append(('/program_search/', 'post', {'search_string':'SearchMatrix'}))
            for route, method, data in routes:
                if system == 'lms' and username:
                    data = {**data,'username':users[username].username}
                r = getattr(client,method)(route,data)
                payload = r.json() if 'application/json' in r.get('Content-Type','') else {}
                results = payload.get('results',[])
                ids = [str(x.get('data',{}).get('id',x.get('id',x.get('course_id')))) for x in results]
                print(json.dumps({'system':system,'role':username or 'anonymous','route':route,'status':r.status_code,'ids':ids,'total':payload.get('total'),'error':payload.get('error')},ensure_ascii=False),flush=True)
                expected_keys = program_ids if route == '/program_search/' else keys
                if system == 'lms':
                    assert r.status_code == 200 and set(ids) == set(keys[:2]), ('LMS catalog search',username,ids)
                elif username == 'py313_staff':
                    assert r.status_code == 200 and ids == [expected_keys[0]], ('staff team isolation',route,ids)
                elif username == 'edx':
                    assert r.status_code == 200 and set(ids) == set(expected_keys[:2]), ('developer positive',route,ids)
                elif username == 'py313_flag':
                    assert r.status_code == 200 and ids == ([] if route == '/program_search/' else keys[1:2]), ('privilege access',route,ids)
                elif system == 'cms':
                    assert r.status_code in (302,403) or (r.status_code == 200 and not ids), ('CMS unprivileged',route,r.status_code,ids)
            if system == 'lms':
                params = {'display_name':'SearchMatrix'}
                if username:
                    params['username'] = users[username].username
                r = client.get('/api/courses/v1/courses/', {**params,'teams_courses_only':'true'})
                team_ids = [x['id'] for x in r.json()['results']]
                expected = keys[:2] if username == 'edx' else (keys[:1] if username == 'py313_staff' else [])
                print('teams-only',username,r.status_code,team_ids)
                assert r.status_code == 200 and set(team_ids) == set(expected)
            for org in ('OTHERORG','*'):
                r = client.get('/api/courses/v1/courses/', {'org':org,'search_term':'SearchMatrix'})
                ids = [x['id'] for x in r.json().get('results',[])] if r.status_code == 200 else []
                print('org-boundary',system,username,org,r.status_code,ids)
                if system == 'lms':
                    expected = keys[:2] if org == '*' else []
                else:
                    expected = (keys[:2] if username == 'edx' else keys[:1] if username == 'py313_staff' else keys[1:2] if username == 'py313_flag' else []) if org == '*' else []
                assert r.status_code in (200,403) and set(ids) == set(expected)
            r = client.get('/api/courses/v1/courses/', {'search_term':'NoMatch'+suffix})
            assert r.status_code in (200,403) and (r.status_code != 200 or not r.json()['results'])
        transaction.set_rollback(True)
print('PASS real search role matrix; SQL rolled back; dedicated ES index retained')
