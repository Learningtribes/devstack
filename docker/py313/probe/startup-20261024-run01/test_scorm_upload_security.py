"""Exercise SCORM upload rejection paths against the real Studio handler."""
import io
import sys
import zipfile

sys.path.insert(0, "/edx/app/edxapp/edx-platform")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from opaque_keys.edx.keys import CourseKey

from cms.djangoapps.contentstore.views.component import component_handler
from xmodule.modulestore.django import modulestore


COURSE = CourseKey.from_string("course-v1:PY313+RuntimeChrome26+2026")
store = modulestore()
block = next(item for item in store.get_items(COURSE) if item.category == "scormxblock")
original_launch = store.get_item(block.location).scorm_pkg
factory = RequestFactory()
users = get_user_model().objects


def upload(user, payload, filename):
    request = factory.post(
        "/xblock/scorm/upload",
        {"scorm_pkg": SimpleUploadedFile(filename, payload, content_type="application/zip")},
        HTTP_HOST="localhost:18010",
    )
    request.user = user
    return component_handler(request, str(block.location), "studio_upload_files")


def assert_unchanged(label):
    current = store.get_item(block.location).scorm_pkg
    assert current == original_launch, f"{label} changed launch path to {current}"


response = upload(users.get(username="edx"), b"not a zip", "malformed.zip")
assert response.status_code == 400, (response.status_code, response.content)
print("malformed upload:", response.status_code, response.content.decode())
assert_unchanged("malformed upload")

manifest = zipfile.ZipFile("/startup/fixtures/py313-scorm12.zip").read("imsmanifest.xml")
manifest = manifest.replace(b"</resource>", b'<file href="../escape-py313.txt"/></resource>')
payload = io.BytesIO()
with zipfile.ZipFile(payload, "w") as archive:
    archive.writestr("imsmanifest.xml", manifest)
    archive.writestr("index.html", "ok")
    archive.writestr("../escape-py313.txt", "escape")
response = upload(users.get(username="edx"), payload.getvalue(), "traversal.zip")
assert response.status_code == 400, (response.status_code, response.content)
print("traversal upload:", response.status_code, response.content.decode())
assert_unchanged("traversal upload")

try:
    upload(users.get(username="py313_staff"), b"not a zip", "unauthorized.zip")
except Exception as exc:
    print("unauthorized upload:", type(exc).__name__)
else:
    raise AssertionError("unauthorized upload unexpectedly returned")
assert_unchanged("unauthorized upload")

print("PASS SCORM malformed, traversal, and unauthorized uploads leave state unchanged")
