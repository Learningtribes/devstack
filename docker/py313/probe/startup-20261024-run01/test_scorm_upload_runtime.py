"""Exercise the real multipart Studio handler and persisted SCORM filesystem."""
from pathlib import Path
import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from opaque_keys.edx.keys import CourseKey
from contentstore.views.component import component_handler
from xmodule.modulestore.django import modulestore

from acceptance_context import course_key
course = course_key()
store = modulestore()
block = next(item for item in store.get_items(course) if item.category == 'scormxblock')
fixture = Path('/startup/fixtures/py313-scorm12.zip').read_bytes()
request = RequestFactory(HTTP_HOST='localhost:18010').post('/xblock/scorm/upload', {
    'scorm_pkg': SimpleUploadedFile('py313-scorm12.zip', fixture, content_type='application/zip'),
})
request.user = get_user_model().objects.get(username='py313_staff')
response = component_handler(request, str(block.location), 'studio_upload_files')
assert response.status_code == 200, (response.status_code, response.content.decode())
assert json.loads(response.content)['status'] == 'success'
saved = store.get_item(block.location)
assert saved.scorm_pkg.endswith('/index.html'), saved.scorm_pkg
assert saved.scorm_pkg_filename == 'py313-scorm12.zip'
assert saved.fs.exists(saved.scorm_pkg)
assert saved.fs.exists(saved.scorm_pkg.split('/')[0] + '.zip')
assert b'LMSInitialize' in saved.fs.readbytes(saved.scorm_pkg)
print('PASS real multipart handler, manifest, extracted SCO and original ZIP')
print('SCORM usage:', saved.location)
print('SCORM launch:', saved.scorm_pkg)
print('This is backend proof; browser upload/save/publish acceptance remains separate.')
