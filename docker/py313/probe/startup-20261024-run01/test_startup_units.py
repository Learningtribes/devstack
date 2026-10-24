"""Focused runtime regressions independent of unfinished platform app registration."""
import sys
import unittest
sys.path.insert(0, '/edx/app/edxapp/edx-platform')
from django.conf import settings
settings.configure(USE_I18N=True, LANGUAGE_CODE='en', INSTALLED_APPS=[])
import django
django.setup()
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import translation
from openedx.core.lib.celery.language import respect_language
from openedx.core.djangoapps.request_cache.middleware import RequestCache, request_cached

class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.saved=translation.get_language()
        self.addCleanup(translation.activate,self.saved)
        translation.activate('en')
    def test_selected_language_and_restore(self):
        with respect_language('fr'):
            self.assertEqual(translation.get_language(),'fr')
        self.assertEqual(translation.get_language(),'en')
    def test_empty_language_preserves_callers_language(self):
        for value in [None,'']:
            with self.subTest(value=value), respect_language(value):
                self.assertEqual(translation.get_language(),'en')
    def test_error_restores_language(self):
        with self.assertRaises(RuntimeError):
            with respect_language('fr'):
                raise RuntimeError('task failed')
        self.assertEqual(translation.get_language(),'en')
    def test_nested_context_restores_outer_language(self):
        with respect_language('fr'):
            with respect_language('de'):
                self.assertEqual(translation.get_language(),'de')
            self.assertEqual(translation.get_language(),'fr')

class RequestCacheTests(unittest.TestCase):
    def setUp(self):
        RequestCache.clear_request_cache()
        self.addCleanup(RequestCache.clear_request_cache)
    def test_real_middleware_clears_before_and_after_response(self):
        cache=RequestCache.get_request_cache()
        cache.data['stale']=True
        def view(request):
            self.assertEqual(RequestCache.get_request_cache().data,{})
            RequestCache.get_request_cache().data['temporary']=True
            return HttpResponse('ok')
        response=RequestCache(view)(RequestFactory().get('/'))
        self.assertEqual(response.content,b'ok')
        self.assertEqual(RequestCache.get_request_cache().data,{})
    def test_exception_hook_clears_state(self):
        middleware=RequestCache(lambda request: HttpResponse())
        RequestCache.get_request_cache().data['temporary']=True
        self.assertIsNone(middleware.process_exception(RequestFactory().get('/'),RuntimeError()))
        self.assertEqual(RequestCache.get_request_cache().data,{})
    def test_decorator_caches_until_next_request(self):
        calls=[]
        @request_cached
        def operation(value, *, suffix):
            calls.append(value)
            return value+suffix
        self.assertEqual(operation('x',suffix='y'),'xy')
        self.assertEqual(operation('x',suffix='y'),'xy')
        self.assertEqual(calls,['x'])
        RequestCache.clear_request_cache()
        operation('x',suffix='y')
        self.assertEqual(calls,['x','x'])

if __name__=='__main__':
    unittest.main(verbosity=2)
