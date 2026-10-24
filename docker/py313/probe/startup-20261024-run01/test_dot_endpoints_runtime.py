"""Real routed DOT endpoints and MySQL lifecycle; all rows roll back.

No mocked authentication, printed credentials or bypass of token validation.
"""
from datetime import timedelta
import base64
import hashlib
import secrets

import django

django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.test import Client
from django.utils import timezone
from oauth2_provider.models import Application, AccessToken, RefreshToken, Grant
from openedx.core.djangoapps.oauth_dispatch.models import ApplicationAccess, RestrictedApplication
from student.models import UserProfile


client = Client(enforce_csrf_checks=True, HTTP_HOST='localhost:18000')


def token(data, status, error=None):
    response = client.post('/oauth2/access_token', data)
    assert response.status_code == status, ('token status', response.status_code)
    body = response.json()
    if error:
        assert body.get('error') == error, ('unexpected error', body.get('error'))
    return body


with transaction.atomic():
    suffix = secrets.token_hex(5)
    password = secrets.token_urlsafe(32)
    user = get_user_model().objects.create_user(
        username='dot_lifecycle_' + suffix, email=suffix + '@example.test', password=password,
    )
    UserProfile.objects.get_or_create(user=user, defaults={'name': 'DOT lifecycle acceptance'})
    secret = secrets.token_urlsafe(32)
    app = Application.objects.create(
        user=user, name='runtime-lifecycle-' + suffix,
        client_type=Application.CLIENT_CONFIDENTIAL, client_secret=secret,
        authorization_grant_type=Application.GRANT_PASSWORD,
    )
    assert check_password(secret, app.client_secret)
    base = {'client_id': app.client_id, 'client_secret': secret,
            'grant_type': 'password', 'username': user.username, 'password': password,
            'scope': 'read'}
    token({**base, 'client_id': 'invalid-' + suffix}, 401, 'invalid_client')
    token({**base, 'client_secret': 'invalid'}, 401, 'invalid_client')
    token({**base, 'scope': 'never:configured'}, 400, 'invalid_scope')
    token({**base, 'password': 'invalid'}, 400, 'invalid_grant')
    issued = token(base, 200)
    access = AccessToken.objects.get(token=issued['access_token'])
    assert access.user_id == user.pk and access.scope == 'read' and not access.is_expired()
    assert RefreshToken.objects.filter(token=issued['refresh_token']).exists()
    login_response = client.post('/oauth2/login/', HTTP_AUTHORIZATION='Bearer ' + issued['access_token'])
    assert login_response.status_code == 204, ('token-to-session login', login_response.status_code)
    refreshed = token({'grant_type': 'refresh_token', 'client_id': app.client_id,
                      'client_secret': secret, 'refresh_token': issued['refresh_token']}, 200)
    assert refreshed['access_token'] != issued['access_token']
    assert not AccessToken.objects.filter(token=issued['access_token']).exists()
    protected = '/api/dot/v0/application/' + user.email
    response = client.get(protected, HTTP_AUTHORIZATION='Bearer ' + refreshed['access_token'])
    # The real API requires staff: an authenticated ordinary token must be denied.
    assert response.status_code == 403, ('bearer role boundary', response.status_code)
    current = AccessToken.objects.get(token=refreshed['access_token'])
    current.expires = timezone.now() - timedelta(seconds=1)
    current.save(update_fields=['expires'])
    assert client.get(protected, HTTP_AUTHORIZATION='Bearer ' + refreshed['access_token']).status_code == 401
    revoked = client.post('/oauth2/revoke_token', {
        'client_id': app.client_id, 'client_secret': secret,
        'token': refreshed['refresh_token'], 'token_type_hint': 'refresh_token',
    })
    assert revoked.status_code == 200
    token({'grant_type': 'refresh_token', 'client_id': app.client_id,
           'client_secret': secret, 'refresh_token': refreshed['refresh_token']}, 400, 'invalid_grant')
    code_app = Application.objects.create(
        user=user, name='runtime-code-' + suffix, client_secret=secret,
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris='http://localhost:18000/dot-acceptance-callback',
    )
    code = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    Grant.objects.create(user=user, application=code_app, code=code, scope='read',
                         expires=timezone.now() + timedelta(minutes=2),
                         code_challenge=challenge, code_challenge_method='S256',
                         redirect_uri=code_app.redirect_uris)
    code_request = {'grant_type': 'authorization_code', 'client_id': code_app.client_id,
           'client_secret': secret, 'code': code, 'code_verifier': verifier,
           'redirect_uri': 'http://localhost:18000/incorrect-callback'}
    denied = token(code_request, 400, 'invalid_request')
    assert denied.get('error_description') == 'Mismatching redirect URI.'
    token({**code_request, 'redirect_uri': code_app.redirect_uris}, 200)
    token({**code_request, 'redirect_uri': code_app.redirect_uris}, 400, 'invalid_grant')
    service_app = Application.objects.create(
        user=user, name='runtime-service-' + suffix, client_secret=secret,
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
    )
    service_request = {'client_id': service_app.client_id, 'client_secret': secret,
                       'grant_type': 'client_credentials', 'scope': 'grades:read'}
    token(service_request, 400, 'invalid_scope')
    ApplicationAccess.objects.create(application=service_app, scopes=['grades:read'])
    service_token = token(service_request, 200)
    assert AccessToken.objects.get(token=service_token['access_token']).user_id == user.pk
    assert client.post('/oauth2/login/', HTTP_AUTHORIZATION='Bearer ' + service_token['access_token']).status_code == 401
    revoked_access = client.post('/oauth2/revoke_token', {
        'client_id': service_app.client_id, 'client_secret': secret,
        'token': service_token['access_token'], 'token_type_hint': 'access_token',
    })
    assert revoked_access.status_code == 200
    assert client.get(protected, HTTP_AUTHORIZATION='Bearer ' + service_token['access_token']).status_code == 401
    RestrictedApplication.objects.create(application=service_app)
    restricted_token = token(service_request, 200)
    assert restricted_token['expires_in'] < 0
    assert AccessToken.objects.get(token=restricted_token['access_token']).is_expired()
    assert client.get(protected, HTTP_AUTHORIZATION='Bearer ' + restricted_token['access_token']).status_code == 401
    assert client.get('/oauth2/get_cookie/').status_code == 400
    assert client.get('/oauth2/get_cookie/', {'user': 'invalid-' + suffix}).status_code == 400
    assert client.post('/oauth2/get_cookie/').status_code == 401  # Bearer authentication is required; no cookie-only login.
    transaction.set_rollback(True)
print('PASS: routed DOT issue/refresh/revoke, PKCE code single-use, hash/expiry/invalid-input negatives, password-token session, service/restricted-token rejection, application scope gate, invalid cookie requests')
