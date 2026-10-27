"""Verify actual browser ILT data and routed learner management boundaries."""
import json
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from courseware.models import XModuleUserStateSummaryField
from opaque_keys.edx.keys import UsageKey

from acceptance_context import block_key
usage = block_key('ilt')
base = f'/courses/{usage.course_key}/xblock/{usage}/handler/'
learner = get_user_model().objects.get(username='py313_learner')
assert not learner.is_staff and not learner.is_superuser
stored = json.loads(XModuleUserStateSummaryField.objects.get(usage_id=usage, field_name='enrolled_users').value)
assert stored['1'][str(learner.pk)]['status'] == 'confirmed'
print('PASS actual browser ordinary learner enrollment persisted as confirmed')
client = Client(HTTP_HOST=settings.LMS_BASE)
credentials = json.loads(Path('/startup/.acceptance-credentials.json').read_text())['learner']
response = client.post('/login_ajax', {'email': credentials['email'], 'password': credentials['password']})
assert response.status_code == 200 and response.json().get('success')
for handler in ('add_session', 'del_session', 'grade_users', 'batch_enroll', 'batch_unenroll', 'update_ack_attendance', 'batch_update_accepted_requests', 'batch_switch_session', 'batch_accept_requests'):
    response = client.post(base + handler, '{}', content_type='application/json')
    assert response.status_code == 401, (handler, response.status_code)
    print('PASS ordinary learner management denied:', handler, response.status_code)
response = client.get(base + 'get_enrolled_users', {'session':'1'})
assert response.status_code == 401, response.status_code
print('PASS ordinary learner roster export denied')
response = client.get(base + 'student_handler')
assert response.status_code == 200, response.status_code
payload = response.json()
assert payload['enrollment'][1]['status'] == 'confirmed'
assert not payload['all_list'] and not payload['accommodation_list'], 'Learner response exposes management rosters'
print('PASS learner sees only own enrollment, no management rosters')
# Reuse the actual role gate: staff must still see management enrollment data.
credentials = json.loads(Path('/startup/.acceptance-credentials.json').read_text())['staff']
client = Client(HTTP_HOST=settings.LMS_BASE)
response = client.post('/login_ajax', {'email': credentials['email'], 'password': credentials['password']})
assert response.status_code == 200 and response.json().get('success')
response = client.get(base + 'student_handler')
assert response.status_code == 200
payload = response.json()
assert payload['is_staff'] and payload['all_list']['1']
assert any(item['user_id'] == str(learner.pk) for item in payload['all_list']['1'])
response = client.get(base + 'get_enrolled_users', {'session': '1'})
assert response.status_code == 200 and any(item['username'] == learner.username for item in response.json())
assert json.loads(XModuleUserStateSummaryField.objects.get(usage_id=usage, field_name='enrolled_users').value) == stored
print('PASS staff retains management roster/export; denied learner requests did not mutate enrollments')
