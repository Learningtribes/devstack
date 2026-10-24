"""Real Django request/cookie language probes, without a platform database."""
import json
import unittest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.utils.translation import get_language_from_request
from openedx.core.djangoapps.lang_pref.views import update_session_language
from openedx.core.djangoapps.lang_pref.middleware import LanguagePreferenceMiddleware

class LanguageTests(unittest.TestCase):
    def test_cookie_round_trip(self):
        request = RequestFactory().patch('/lang_pref/session_language',
            data=json.dumps({'pref-lang':'fr'}), content_type='application/json')
        response=update_session_language(request)
        self.assertEqual(response.status_code,200)
        cookie=response.cookies[settings.LANGUAGE_COOKIE_NAME]
        self.assertEqual(cookie.value,'fr')
        self.assertEqual(bool(cookie['secure']),bool(settings.SESSION_COOKIE_SECURE))
        follow=RequestFactory().get('/')
        follow.COOKIES[settings.LANGUAGE_COOKIE_NAME]=cookie.value
        with override_settings(LANGUAGES=[('en','English'),('fr','French')]):
            self.assertEqual(get_language_from_request(follow),'fr')
    def test_invalid_payloads(self):
        for body in ['{','[]','{"pref-lang": 42}','{"pref-lang": "invalid-xyz"}']:
            request=RequestFactory().patch('/lang_pref/session_language',data=body,content_type='application/json')
            self.assertEqual(update_session_language(request).status_code,400)
    def test_anonymous_change_precedes_existing_cookie(self):
        request=RequestFactory().get('/',HTTP_ACCEPT_LANGUAGE='en')
        request.user=AnonymousUser()
        request.COOKIES={settings.LANGUAGE_COOKIE_NAME:'en','change-'+settings.LANGUAGE_COOKIE:'fr'}
        middleware=LanguagePreferenceMiddleware(lambda request:HttpResponse())
        middleware.process_request(request)
        with override_settings(LANGUAGES=[('en','English'),('fr','French')]):
            self.assertEqual(get_language_from_request(request),'fr')
        response=middleware.process_response(request,HttpResponse())
        self.assertEqual(response.cookies['change-'+settings.LANGUAGE_COOKIE]['max-age'],0)

suite=unittest.defaultTestLoader.loadTestsFromTestCase(LanguageTests)
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful(): raise SystemExit(1)
