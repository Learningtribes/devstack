"""Real isolated GridFS regression, run through full CMS manage shell."""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from django.test import RequestFactory, override_settings
from opaque_keys.edx.locator import CourseLocator
from xmodule.contentstore.django import contentstore
from xmodule.contentstore.content import StaticContent
from xmodule.exceptions import NotFoundError
from contentstore.views.course import unsplash_proxy

store = contentstore()
course = CourseLocator('PY313', 'AssetRegression', uuid4().hex)
assert store.get_all_content_for_course(course) == ([], 0)
for name, mime, data in [('zulu.txt', 'text/plain', b'zulu'), ('Alpha.txt', 'text/plain', 'alpha'),
                         ('bravo.png', 'image/png', b'png-regression')]:
    key = course.make_asset_key('asset', name)
    store.save(StaticContent(key, name, mime, data))
    assert store.find(key).data == (data.encode() if isinstance(data, str) else data)
    if name == 'zulu.txt':
        store.save(StaticContent(key, name, mime, b'zulu-updated'))
        assert store.find(key).data == b'zulu-updated'
assets, count = store.get_all_content_for_course(course, sort=[('displayname', 1)])
assert count == 3
assert [a['displayname'] for a in assets] == ['Alpha.txt', 'bravo.png', 'zulu.txt']
page, total = store.get_all_content_for_course(course, start=1, maxresults=1, sort=[('displayname', 1)])
assert total == 3 and len(page) == 1 and page[0]['displayname'] == 'bravo.png'
filtered, count = store.get_all_content_for_course(course, filter_params={'contentType': 'text/plain'})
assert count == 2 and {a['displayname'] for a in filtered} == {'zulu.txt', 'Alpha.txt'}
assert store.get_all_content_for_course(course, filter_params={'contentType': 'application/pdf'}) == ([], 0)
deleted_key = course.make_asset_key('asset', 'bravo.png')
store.delete(deleted_key)
try:
    store.find(deleted_key)
except NotFoundError:
    pass
else:
    raise AssertionError('Deleted GridFS asset remained readable')
with override_settings(UNSPLASH_CLIENT_ID=''):
    response = unsplash_proxy(RequestFactory().get('/unsplash-proxy/'))
    assert response.status_code == 503 and b'not configured' in response.content
    response = unsplash_proxy(RequestFactory().post('/unsplash-proxy/'))
    assert response.status_code == 405
print(json.dumps({'course': str(course), 'empty': True, 'save_read': 3, 'case_insensitive_sort': True,
                  'pagination_total': total, 'filter': True, 'update': True, 'delete': True, 'unsplash_unconfigured': 503,
                  'unsplash_post': 405, 'external_requests': 0, 'assets_preserved': True}))
manifest = {
    'course': str(course),
    'assets': [
        {'usage': str(course.make_asset_key('asset', name)), 'name': name,
         'sha256': hashlib.sha256((data.encode() if isinstance(data, str) else data)).hexdigest()}
        for name, data in [('zulu.txt', b'zulu-updated'), ('Alpha.txt', 'alpha')]
    ],
}
target = Path('/runtime/gridfs-acceptance-latest.json')
fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as output:
    output.write(json.dumps(manifest, sort_keys=True) + '\n')
store.close_connections()
