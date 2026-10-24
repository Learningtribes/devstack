"""Replay existing learner pages through real routes and signed login session."""
import json
from pathlib import Path
import sys
sys.path.insert(0, '/edx/app/edxapp/edx-platform')
import django
django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse

values = json.loads(Path('/startup/.acceptance-credentials.json').read_text())['learner']
u = get_user_model().objects.get(username=values['username'])
assert not u.is_staff and not u.is_superuser
c = Client(HTTP_HOST='localhost:18000')
r = c.post('/login_ajax', {'email': values['email'], 'password': values['password']})
assert r.status_code == 200 and r.json().get('success'), (r.status_code, r.content[:150])
print('ROLE', u.username, 'staff', u.is_staff, 'superuser', u.is_superuser)
for path in ['/dashboard', '/courses/course-v1:PY313+RuntimeChrome26+2026/course/', '/courses/course-v1:PY313+RuntimeChrome26+2026/courseware']:
    r = c.get(path, follow=True)
    body = r.content.decode()
    print('PAGE', path, 'status', r.status_code, 'redirects', r.redirect_chain)
    assert r.status_code == 200, (path, r.status_code)
    assert '平台的服务器发生了错误' not in body and 'Internal Server Error' not in body
print('PASS learner dashboard/course home/courseware without error page')
