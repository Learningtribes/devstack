"""Real routed one-use DOT cookie exchange, session and logout negatives."""
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model, SESSION_KEY
from django.db import transaction
from django.contrib.sessions.backends.db import SessionStore
from openedx.core.djangoapps.safe_sessions.middleware import SafeCookieData
from django.test import Client
from django.utils import timezone
from oauth2_provider.models import Application, AccessToken
from student.models import UserProfile
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration

client = Client(enforce_csrf_checks=True, HTTP_HOST=settings.LMS_BASE)
with transaction.atomic():
    suffix = secrets.token_hex(5)
    user = get_user_model().objects.create_user('cookie_' + suffix)
    UserProfile.objects.create(user=user, name='Cookie exchange acceptance')
    app = Application.objects.create(user=user, name='cookie_' + suffix,
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_PASSWORD)
    def issue():
        return AccessToken.objects.create(user=user, application=app, token=secrets.token_urlsafe(32),
            expires=timezone.now() + timedelta(minutes=2), scope='read')
    token = issue()
    header = {'HTTP_AUTHORIZATION': 'Bearer ' + token.token}
    for destination in ['https://example.invalid/', '//example.invalid/', '\\\\example.invalid/', 'javascript:alert(1)']:
        response = client.post('/oauth2/get_cookie/', {'next': destination}, **header)
        assert response.status_code == 400, (destination, response.status_code)
        assert AccessToken.objects.filter(pk=token.pk).exists()
        saved = client.cookies.get(settings.SESSION_COOKIE_NAME)
        if saved and saved.value:
            anonymous_cookie = SafeCookieData.parse(saved.value)
            assert SESSION_KEY not in SessionStore(anonymous_cookie.session_id)
    response = client.post('/oauth2/get_cookie/', {'next': '/dashboard'}, **header)
    assert response.status_code == 302 and response['Location'] == '/dashboard'
    cookie = SafeCookieData.parse(response.cookies[settings.SESSION_COOKIE_NAME].value)
    assert cookie.verify(user.pk)
    session_id = cookie.session_id
    assert int(SessionStore(session_id)[SESSION_KEY]) == user.pk
    assert settings.SESSION_COOKIE_NAME in response.cookies
    assert bool(response.cookies[settings.SESSION_COOKIE_NAME]['httponly']) == settings.SESSION_COOKIE_HTTPONLY
    assert not AccessToken.objects.filter(pk=token.pk).exists()
    assert client.post('/oauth2/get_cookie/', **header).status_code == 401
    assert client.post('/oauth2/get_cookie/').status_code == 401
    assert client.get('/oauth2/get_cookie/').status_code == 400
    print('PASS one-use bearer exchange; configured signed session cookie flags; redirect and replay boundaries')
    response = client.get('/logout', {'redirect_url': 'https://example.invalid/'})
    assert response.status_code == 302 and response['Location'] == '/'
    assert SESSION_KEY not in SessionStore(session_id)
    assert response.cookies[settings.SESSION_COOKIE_NAME]['max-age'] == 0
    print('PASS logout clears session and rejects external redirect')
    app.authorization_grant_type = Application.GRANT_CLIENT_CREDENTIALS
    app.save(update_fields=['authorization_grant_type'])
    service = issue()
    assert client.post('/oauth2/get_cookie/', HTTP_AUTHORIZATION='Bearer ' + service.token).status_code == 401
    for configuration in SiteConfiguration.objects.all():
        configuration.values = {**configuration.values, 'enable_clientcredentials_type': True}
        configuration.save(update_fields=['values'])
    assert client.post('/oauth2/get_cookie/', HTTP_AUTHORIZATION='Bearer ' + service.token).status_code == 401
    assert AccessToken.objects.filter(pk=service.pk).exists()
    print('PASS service grant rejected even with site client-credentials login flag enabled')
    app.authorization_grant_type = Application.GRANT_PASSWORD
    app.save(update_fields=['authorization_grant_type'])
    user.is_active = False
    user.save(update_fields=['is_active'])
    assert client.post('/oauth2/get_cookie/', HTTP_AUTHORIZATION='Bearer ' + service.token).status_code == 401
    print('PASS service grants and inactive users cannot create cookie sessions')
    transaction.set_rollback(True)
