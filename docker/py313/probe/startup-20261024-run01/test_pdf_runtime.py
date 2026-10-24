"""Real routed PDF asset upload/content modification boundaries and bytes."""
import hashlib
import json
from pathlib import Path
import requests
from opaque_keys.edx.keys import UsageKey
from xmodule.modulestore.django import modulestore

values = json.loads(Path('/startup/.acceptance-credentials.json').read_text())
usage = UsageKey.from_string('block-v1:PY313+CleanRebuild28+2026+type@pdf+block@6399061df9c247c49d4233661d101ba4')
store = modulestore()
block = store.get_item(usage)
before = (block.display_name, block.url, block.allow_download)
assert before[0] == 'Run36 local PDF'
fixture = Path('/startup/fixtures/py313-textbook.pdf').read_bytes()
session = requests.Session()
base = 'http://localhost:18000'
session.get(base + '/login')
credentials = values['learner']
r = session.post(base + '/login_ajax', data={'email': credentials['email'], 'password': credentials['password']}, headers={'X-CSRFToken':session.cookies.get('csrftoken',''), 'Referer':base+'/'})
assert r.status_code == 200 and r.json().get('success')
r = session.post(base + f'/courses/{usage.course_key}/xblock/{usage}/handler/save_pdf', json={'display_name': 'denied mutation'}, headers={'X-CSRFToken':session.cookies.get('csrftoken',''), 'Referer':base+'/'})
print('LMS learner content save refused', r.status_code, flush=True)
assert r.status_code == 403
response = session.get(block.url.replace('localhost:18120', 'localhost:18000'))
print('asset response', response.status_code, len(response.content), flush=True)
assert response.status_code == 200 and response.content == fixture
print('PASS actual published PDF bytes', len(fixture), hashlib.sha256(fixture).hexdigest(), flush=True)
for role in ('anonymous', 'learner', 'other_org'):
    session = requests.Session()
    base = 'http://localhost:18010'
    session.get(base + '/signin')
    if role != 'anonymous':
        credentials = values[role]
        r = session.post(base + '/login_ajax', data={'email': credentials['email'], 'password': credentials['password']}, headers={'X-CSRFToken':session.cookies.get('csrftoken',''), 'Referer':base+'/'})
        assert r.status_code == 200 and r.json().get('success')
    headers = {'X-CSRFToken': session.cookies.get('csrftoken', ''), 'Referer': base + '/'}
    r = session.post(base + '/assets/course-v1:PY313+CleanRebuild28+2026/', files={'file': ('denied-run36.pdf', fixture, 'application/pdf')}, headers=headers, allow_redirects=False)
    print('upload refused', role, r.status_code, flush=True)
    assert r.status_code in (302, 403)
    r = session.post(base + '/xblock/' + str(usage) + '/handler/save_pdf', json={'display_name': 'denied mutation'}, headers=headers, allow_redirects=False)
    print('CMS save refused', role, r.status_code, flush=True)
    assert r.status_code in (302, 403)
block = store.get_item(usage)
assert (block.display_name, block.url, block.allow_download) == before
print('PASS PDF CMS upload/save role denials preserve actual browser component', flush=True)

session = requests.Session()
base = 'http://localhost:18010'
session.get(base + '/signin')
credentials = values['staff']
r = session.post(base + '/login_ajax', data={'email': credentials['email'], 'password': credentials['password']}, headers={'X-CSRFToken':session.cookies.get('csrftoken',''), 'Referer':base+'/'})
assert r.status_code == 200 and r.json().get('success')
r = session.post(base + '/xblock/' + str(usage) + '/handler/save_pdf', json={'display_name':block.display_name, 'url':block.url, 'allow_download':'True', 'source_text':block.source_text, 'source_url':block.source_url}, headers={'X-CSRFToken':session.cookies.get('csrftoken',''), 'Referer':base+'/'})
print('CMS staff save remains allowed',r.status_code,flush=True)
assert r.status_code == 200 and r.json()['result'] == 'success'
assert store.get_item(usage).display_name == before[0]
