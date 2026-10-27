"""Real staff ILT enrollment/grading and learner roster isolation in run28."""
import json
from pathlib import Path
import requests
from django.contrib.auth import get_user_model
from courseware.models import StudentModule, XModuleUserStateSummaryField
from opaque_keys.edx.keys import UsageKey

from acceptance_context import block_key
usage = block_key('ilt')
base = 'http://localhost:18000'
route = f'/courses/{usage.course_key}/xblock/{usage}/handler/'
values = json.loads(Path('/startup/.acceptance-credentials.json').read_text())
second = values['learner']
user = get_user_model().objects.get(username=second['username'])

def login(credentials):
    s = requests.Session()
    s.get(base + '/login')
    r = s.post(base + '/login_ajax', data={'email': credentials['email'], 'password': credentials['password']}, headers={'X-CSRFToken': s.cookies.get('csrftoken', ''), 'Referer': base + '/'})
    assert r.status_code == 200 and r.json().get('success')
    return s

def call(s, name, data):
    r = s.post(base + route + name, json=data, headers={'X-CSRFToken':s.cookies.get('csrftoken',''), 'Referer':base+'/'})
    print('handler', name, r.status_code, flush=True)
    assert r.status_code == 200, (name, r.status_code)
    return r.json()

staff = login(values['staff'])
payload = call(staff, 'batch_enroll', {'session': '1', 'identifiers': user.username, 'bypass_validation': True, 'notify_by_email': False})
assert payload['data']['all_list']['1']
stored = json.loads(XModuleUserStateSummaryField.objects.get(usage_id=usage, field_name='enrolled_users').value)
assert stored['1'][str(user.pk)]['status'] == 'confirmed'
print('PASS real staff batch enrollment durable', user.pk, flush=True)
learner = login(second)
r = learner.get(base + route + 'student_handler')
assert r.status_code == 200
payload = r.json()
assert payload['enrollment'][0] == '1' and payload['enrollment'][1]['status'] == 'confirmed'
assert not payload['all_list'] and not payload['accommodation_list']
call(staff, 'update_ack_attendance', {'sess_key': '1', 'status': True})
assert json.loads(XModuleUserStateSummaryField.objects.get(usage_id=usage, field_name='sessions').value)['1']['ack_attendance_sheet']
call(staff, 'grade_users', {user.username: True, values['other_org']['username']: True})
score = StudentModule.objects.get(student=user, module_state_key=usage)
assert score.grade == 1 and score.max_grade == 1, (score.grade, score.max_grade)
other = get_user_model().objects.get(username=values['other_org']['username'])
assert not StudentModule.objects.filter(student=other, module_state_key=usage, grade__isnull=False).exists()
print('PASS staff grading persisted 1/1 only for enrolled learner; unselected user untouched', flush=True)
print('PASS ILT staff enrollment/attendance/grading and ordinary learner isolation', flush=True)
