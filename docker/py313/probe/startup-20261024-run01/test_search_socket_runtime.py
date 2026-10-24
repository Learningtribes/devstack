"""Real socket search on retained Mongo courses with signed password login."""
import json
from pathlib import Path
import requests

values = json.loads(Path('/startup/.acceptance-credentials.json').read_text())
course = 'course-v1:PY313+DiscussionRun03+2026'
for role in ('staff', 'learner', 'other_org', 'anonymous'):
    for system, port in [('cms',18010),('lms',18000)]:
        base = f'http://localhost:{port}'
        client = requests.Session()
        client.get(base + ('/signin' if system == 'cms' else '/login'))
        if role != 'anonymous':
            user = values[role]
            r=client.post(base+'/login_ajax',data={'email':user['email'],'password':user['password']},headers={'X-CSRFToken':client.cookies.get('csrftoken',''),'Referer':base+'/'})
            assert r.status_code == 200 and r.json().get('success'), (role,system,'login',r.status_code)
        routes = [('/api/courses/v1/courses/', 'get', {'search_term':'Discussion'})]
        if system == 'cms':
            routes += [('/course_search/','post',{'search_string':'Discussion'})]
        for path, method, params in routes:
            r=getattr(client,method)(base+path,**({'params':params} if method=='get' else {'data':params}),allow_redirects=False)
            ids=[]
            if r.status_code == 200:
                ids=[str(x.get('data',{}).get('id',x.get('id'))) for x in r.json()['results']]
            print(system,role,path,r.status_code,ids,flush=True)
            if system == 'lms' or role == 'staff':
                assert r.status_code == 200 and course in ids
            else:
                assert r.status_code in (302,403) or (r.status_code == 200 and not ids)
        for params in [{'search_term':'NoMatchSocket20261024'},{'org':'OTHERORG','search_term':'Discussion'}]:
            r=client.get(base+'/api/courses/v1/courses/',params=params)
            assert r.status_code in (200,403)
            assert r.status_code != 200 or not r.json()['results']
        if role=='learner' and system=='lms':
            for path in ['/dashboard',f'/courses/{course}/course/', '/courses/course-v1:PY313+RuntimeChrome26+2026/courseware']:
                r=client.get(base+path)
                print('learner-regression',path,r.status_code)
                assert r.status_code==200 and 'Internal Server Error' not in r.text
print('PASS real socket search: actual published course positive, tenant/no-match/role negatives, learner pages')
