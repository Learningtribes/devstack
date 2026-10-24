"""Real ordinary learner routes; maintenance rendering is not forum CRUD proof."""
import json
from pathlib import Path
import django

django.setup()
from django.test import Client
from django_comment_common.models import ForumsConfig

values = json.loads(Path('/startup/.acceptance-credentials.json').read_text())['learner']
client = Client(HTTP_HOST='localhost:18000')
r = client.post('/login_ajax', {'email': values['email'], 'password': values['password']})
assert r.status_code == 200 and r.json()['success']
assert not ForumsConfig.current().enabled, 'This probe specifically covers the configured maintenance state'
r = client.get('/courses/course-v1:PY313+DiscussionRun03+2026/discussion/forum/')
print('configured maintenance page', r.status_code)
assert r.status_code == 200
assert b'courseware-error' not in r.content
r = client.get('/courses/course-v1:PY313+DiscussionRun03+2026/discussion/forum/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
print('configured maintenance AJAX', r.status_code)
assert r.status_code == 503
r = client.get('/courses/course-v1:PY313+RuntimeChrome26+2026/discussion/forum/')
print('absent tab', r.status_code)
assert r.status_code == 404
print('PASS maintenance rendering and absent tab rejection; forum CRUD remains unverified')
