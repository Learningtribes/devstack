"""Real database session signing, tamper rejection and JSON idle tracking."""
import secrets
import time
from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.models import User, AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.db import transaction
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from openedx.core.djangoapps.safe_sessions.middleware import SafeCookieData, SafeSessionMiddleware
from openedx.core.djangoapps.session_inactivity_timeout.middleware import SessionInactivityTimeout, LAST_TOUCH_KEYNAME

factory=RequestFactory()
with transaction.atomic(), override_settings(SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_PATH='/'):
    user=User.objects.create(username='session_'+secrets.token_hex(6))
    store=SessionStore()
    store[SESSION_KEY]=str(user.pk)
    store.save()
    cookie=SafeCookieData.create(store.session_key,user.pk)
    assert cookie.verify(user.pk)
    assert not cookie.verify(user.pk+1)
    bad=SafeCookieData.parse(str(cookie))
    bad.signature=bad.signature[:-1]+('a' if bad.signature[-1]!='a' else 'b')
    assert not bad.verify(user.pk)
    with override_settings(SESSION_COOKIE_AGE=-1):
        assert not cookie.verify(user.pk)
    middleware=SafeSessionMiddleware(lambda request:HttpResponse())
    request=factory.get('/local-session')
    request.COOKIES[settings.SESSION_COOKIE_NAME]=str(cookie)
    assert middleware.process_request(request) is None
    assert request.safe_cookie_verified_user_id==user.pk
    request.user=user
    request.session['probe']='persisted'
    response=middleware.process_response(request,HttpResponse())
    saved=response.cookies[settings.SESSION_COOKIE_NAME]
    assert saved['samesite']=='Lax'
    assert SafeCookieData.parse(saved.value).verify(user.pk)
    assert SessionStore(store.session_key)['probe']=='persisted'
    request=factory.get('/local-session')
    request.COOKIES[settings.SESSION_COOKIE_NAME]=str(bad)
    assert middleware.process_request(request).status_code==302
    response=middleware.process_response(request,HttpResponse())
    assert response.cookies[settings.SESSION_COOKIE_NAME]['max-age']==0
    assert response.cookies[settings.SESSION_COOKIE_NAME]['samesite']=='Lax'
    idle=SessionInactivityTimeout(lambda request:HttpResponse())
    request=factory.get('/local-session')
    request.user=user
    request.session=SessionStore()
    request.session[SESSION_KEY]=str(user.pk)
    with override_settings(SESSION_INACTIVITY_TIMEOUT_IN_SECONDS=60):
        idle.process_request(request)
        assert isinstance(request.session[LAST_TOUCH_KEYNAME],float)
        request.session.save()
        assert isinstance(SessionStore(request.session.session_key)[LAST_TOUCH_KEYNAME],float)
        request.session[LAST_TOUCH_KEYNAME]=time.time()-120
        idle.process_request(request)
        assert request.user.is_anonymous
        assert SESSION_KEY not in request.session
    transaction.set_rollback(True)
print('PASS: bound/tampered/expired cookies, database JSON session write/read, cookie flags/deletion and idle logout')
