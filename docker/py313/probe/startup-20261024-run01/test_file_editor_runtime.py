"""Real Studio File editor output, accept metadata and readonly display."""
import json
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from opaque_keys.edx.keys import UsageKey
from xmodule.modulestore.django import modulestore
v=json.loads(Path('/startup/.acceptance-credentials.json').read_text())['staff']
metadata=json.loads(Path('/runtime/scorm-acceptance-latest.json').read_text())
usage=UsageKey.from_string(metadata['usage'])
block=modulestore().get_item(usage)
s=requests.Session();base='http://localhost:18010';s.get(base+'/signin')
r=s.post(base+'/login_ajax',data={'email':v['email'],'password':v['password']},headers={'X-CSRFToken':s.cookies.get('csrftoken',''),'Referer':base+'/'})
assert r.status_code==200 and r.json().get('success')
r=s.get(base+f'/xblock/{usage}/studio_view', headers={'Accept':'application/json'})
assert r.status_code==200,r.status_code
payload=r.json(); html=payload['html']; soup=BeautifulSoup(html,'html.parser')
assert soup.select_one('input[type=file]#xb-field-edit-scorm_pkg')['accept']=='application/zip'
assert soup.select_one('input[type=file]#xb-field-edit-cover_image')['accept']=='image/*'
assert not soup.select_one('input#xb-field-edit-scorm_pkg_filename')
assert block.scorm_pkg_filename in soup.get_text()
assert block.cover_images and all(candidate in html for candidate in block.cover_images)
print('PASS actual Studio File editor: ZIP/image accept metadata; readonly filename has no editable input; stored cover candidates rendered')
print('Readonly is editor metadata; upload accept hints do not replace existing ZIP/path validation, tested separately.')
