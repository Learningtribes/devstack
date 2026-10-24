"""Targeted regressions using real DOT models in an ephemeral SQLite database.

This isolated unit suite does not replace platform schema or HTTP acceptance.
"""
import sys
sys.path.extend(["/edx/app/edxapp/edx-platform/common/djangoapps", "/edx/app/edxapp/edx-platform/openedx/core/djangoapps"])
import importlib.util
from pathlib import Path
import tempfile
import csv
import io
import codecs
import unittest
from datetime import timedelta

from django.conf import settings
settings.configure(MICROSITE_TEMPLATE_BACKEND=None, MICROSITE_BACKEND='microsite_configuration.backends.base.BaseMicrositeBackend', SECRET_KEY='ephemeral-unit-suite', USE_TZ=True,
    DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
    INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'oauth2_provider'],
    OAUTH2_PROVIDER={'SCOPES': {'read': 'Read', 'write': 'Write'}},
    DEFAULT_AUTO_FIELD='django.db.models.AutoField',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.PBKDF2PasswordHasher'])
import django
django.setup()
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.test import RequestFactory
from django.utils import timezone
from oauth2_provider.models import Application, AccessToken
from rest_framework.exceptions import AuthenticationFailed
from openedx.core.lib.api.authentication import OAuth2AuthenticationAllowInactiveUser, OAuth2Authentication
import markdown


def load_extension(name):
    path = Path('/edx/app/edxapp/edx-platform/lms/djangoapps/course_wiki/plugins/markdownedx') / (name+'.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BearerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        call_command('migrate', verbosity=0)
        cls.user = get_user_model().objects.create_user('unit-only-user', is_active=False)
        cls.app = Application.objects.create(user=cls.user, client_type='confidential',
            authorization_grant_type='password', client_secret='ephemeral-test-value')
        cls.valid = AccessToken.objects.create(user=cls.user, application=cls.app,
            token='unit-valid-token', expires=timezone.now()+timedelta(minutes=5), scope='read')
        AccessToken.objects.create(user=cls.user, application=cls.app,
            token='unit-expired-token', expires=timezone.now()-timedelta(minutes=5), scope='read')

    def auth(self, header):
        return OAuth2AuthenticationAllowInactiveUser().authenticate(
            RequestFactory().get('/api', HTTP_AUTHORIZATION=header))

    def test_dot_secret_hashed(self):
        self.assertNotEqual(self.app.client_secret, 'ephemeral-test-value')
        self.assertTrue(check_password('ephemeral-test-value', self.app.client_secret))

    def test_bearer_valid_inactive_user_allowed(self):
        user, token = self.auth('Bearer unit-valid-token')
        self.assertEqual(user.pk, self.user.pk)
        self.assertEqual(token.pk, self.valid.pk)

    def test_expired_unknown_and_malformed_rejected(self):
        for header in ['Bearer unit-expired-token', 'Bearer absent', 'Bearer', 'Bearer a b']:
            with self.subTest(header=header), self.assertRaises(AuthenticationFailed):
                self.auth(header)

    def test_active_authentication_rejects_inactive(self):
        with self.assertRaises(AuthenticationFailed):
            OAuth2Authentication().authenticate(RequestFactory().get('/api',
                HTTP_AUTHORIZATION='Bearer unit-valid-token'))

    def test_other_auth_ignored(self):
        self.assertIsNone(self.auth('Basic irrelevant'))

    def test_revoked_rejected(self):
        token = AccessToken.objects.create(user=self.user, application=self.app,
            token='unit-revoked', expires=timezone.now()+timedelta(minutes=5), scope='read')
        token.revoke()
        with self.assertRaises(AuthenticationFailed):
            self.auth('Bearer unit-revoked')


class StorageTests(unittest.TestCase):
    def test_report_csv_and_file_links(self):
        from lms.djangoapps.instructor_task.models import DjangoStorageReportStore
        from openedx.core.storage import get_storage
        with tempfile.TemporaryDirectory() as directory:
            self.addCleanup(get_storage.cache_clear)
            store = DjangoStorageReportStore('django.core.files.storage.FileSystemStorage',
                {'location': directory, 'base_url': '/reports/'})
            course = 'course-v1:Local+Compat+2026'
            store.store_rows(course, 'unicode.csv', [['名称', 'naïve', {'result': '成功'}]])
            with store.storage.open(store.path_to(course, 'unicode.csv'), 'rb') as stream:
                data = stream.read()
            self.assertTrue(data.startswith(codecs.BOM_UTF8))
            row = next(csv.reader(io.StringIO(data.decode('utf-8-sig')), delimiter=';'))
            self.assertEqual(row, ['名称', 'naïve', '{"result": "成功"}'])
            self.assertEqual(store.links_for(course)[0][0], 'unicode.csv')
            self.assertEqual(store.links_for('absent-course'), [])

    def test_s3_options_without_network(self):
        from openedx.core.storage import S3ReportStorage
        storage = S3ReportStorage(acl='private', bucket='local-unit-only',
            custom_domain='assets.example.invalid', access_key='unit', secret_key='unit')
        self.assertEqual(storage.default_acl, 'private')
        self.assertEqual(storage.bucket_name, 'local-unit-only')
        self.assertEqual(storage.custom_domain, 'assets.example.invalid')

    def test_setting_event_truncation_integer_limit(self):
        from django.test import override_settings
        from util.model_utils import truncate_fields
        with override_settings(TRACK_MAX_EVENT=20):
            self.assertEqual(truncate_fields('abcdefgh', 'xyz'),
                {'old': 'abcde', 'new': 'xyz', 'truncated': ['old']})


class FilesystemTests(unittest.TestCase):
    def test_memory_and_osfs_roundtrip_and_missing(self):
        from fs import open_fs
        from fs.errors import ResourceNotFound
        with open_fs('mem://') as filesystem:
            filesystem.writetext('content.txt', '课程')
            self.assertEqual(filesystem.readtext('content.txt'), '课程')
            with self.assertRaises(ResourceNotFound):
                filesystem.readtext('absent')
        with tempfile.TemporaryDirectory() as directory, open_fs(directory) as filesystem:
            filesystem.writetext('content.txt', 'persistent')
            self.assertEqual((Path(directory) / 'content.txt').read_text(), 'persistent')

    def test_external_entrypoint_registry(self):
        from fs.opener.registry import Registry
        from importlib.metadata import entry_points
        registry = Registry(load_extern=True)
        for entry in entry_points(group='fs.opener'):
            self.assertIn(entry.name, registry.protocols)
        from fs.opener.osfs import OSFSOpener
        registry.install(OSFSOpener)
        self.assertIn('osfs', registry.get_opener('osfs').protocols)


class MarkdownTests(unittest.TestCase):
    def test_math_render_and_escape(self):
        ext = load_extension('mdx_mathjax').MathJaxExtension()
        html = markdown.markdown('Equation $x+y$ and $$z$$', extensions=[ext])
        self.assertIn('<span>$x+y$</span>', html)
        self.assertIn('<span>$$z$$</span>', html)
        html = markdown.markdown(r'Escaped \$x\$ and `$y$`', extensions=[ext])
        self.assertNotIn('<span>', html)

    def test_video_respects_links_and_code(self):
        ext = load_extension('mdx_video').VideoExtension()
        url = 'http://www.youtube.com/watch?v=abc'
        self.assertIn('<object ', markdown.markdown(url, extensions=[ext]))
        self.assertNotIn('<object ', markdown.markdown(f'`{url}`', extensions=[ext]))
        self.assertNotIn('<object ', markdown.markdown(f'[video]({url})', extensions=[ext]))

if __name__ == '__main__':
    unittest.main(verbosity=2)
