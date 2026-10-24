"""Exercise real Django transactions and request-cache restoration without platform DBs."""
import sys
import unittest
sys.path[:0] = ['/edx/app/edxapp/edx-platform', '/edx/app/edxapp/edx-platform/common/djangoapps']
from django.conf import settings
settings.configure(SECRET_KEY='ephemeral-unit-only', INSTALLED_APPS=[],
    DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}})
import django
django.setup()
from django.db import connection, transaction
from util.db import outer_atomic, enable_named_outer_atomic, OUTER_ATOMIC_CACHE_NAME
from openedx.core.djangoapps.request_cache import get_cache, clear_cache

class OuterAtomicTests(unittest.TestCase):
    def setUp(self):
        clear_cache(OUTER_ATOMIC_CACHE_NAME)
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE test_atomic (id INTEGER PRIMARY KEY)')
        self.addCleanup(self.drop_table)
        self.addCleanup(clear_cache, OUTER_ATOMIC_CACHE_NAME)
    def drop_table(self):
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE test_atomic')
    def test_commit_and_rollback(self):
        with outer_atomic():
            with connection.cursor() as cursor: cursor.execute('INSERT INTO test_atomic VALUES (1)')
        with self.assertRaises(ValueError):
            with outer_atomic():
                with connection.cursor() as cursor: cursor.execute('INSERT INTO test_atomic VALUES (2)')
                raise ValueError('rollback')
        with connection.cursor() as cursor:
            cursor.execute('SELECT id FROM test_atomic')
            self.assertEqual(cursor.fetchall(), [(1,)])
        self.assertTrue(connection.get_autocommit())
    def test_nested_rejected_and_disabled_name_allowed(self):
        with transaction.atomic():
            with self.assertRaises(transaction.TransactionManagementError):
                with outer_atomic(): pass
            with outer_atomic(name='disabled'): pass
            with enable_named_outer_atomic('enabled'):
                with self.assertRaises(transaction.TransactionManagementError):
                    with outer_atomic(name='enabled'): pass
    def test_exception_and_reentrant_name_restoration(self):
        cache=get_cache(OUTER_ATOMIC_CACHE_NAME)
        with self.assertRaises(ValueError):
            with enable_named_outer_atomic('enabled'):
                with enable_named_outer_atomic('enabled'): pass
                self.assertTrue(cache['enabled'])
                raise ValueError('cleanup')
        self.assertNotIn('enabled', cache)
if __name__=='__main__': unittest.main(verbosity=2)
