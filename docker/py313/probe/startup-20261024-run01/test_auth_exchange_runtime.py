"""Real production LT-02 route rejection; SQL fixtures and sessions roll back.

Run only via run_auth_exchange_acceptance.py in a fresh settings process.
No authentication mocks, provider calls, issued tokens or existing data edits.
"""
import json
import socket
import sys
from collections import Counter

# Audit before setup. Only the local SQL and cache transports are permitted.
network = []
allowed_hosts = {'mysql', 'memcached'}
allowed_ips = set()
for hostname in allowed_hosts:
    allowed_ips.update(info[4][0] for info in socket.getaddrinfo(hostname, None))


def network_audit(event, args):
    if event == 'socket.getaddrinfo':
        host = args[0]
        network.append({'event': event, 'host': str(host)})
        if host not in allowed_hosts and host not in allowed_ips:
            raise AssertionError('External DNS forbidden')
    elif event == 'socket.sendto':
        address = args[-1]
        network.append({'event': event, 'address': str(address)})
        if not isinstance(address, tuple) or address[0] not in {'localhost', '127.0.0.1', '::1'} or address[1] != 8125:
            raise AssertionError('External datagram forbidden')
    elif event == 'socket.connect':
        address = args[1]
        network.append({'event': event, 'address': str(address)})
        if not isinstance(address, tuple) or address[0] not in allowed_ips or address[1] not in {3306, 11211}:
            raise AssertionError('External connection forbidden')


sys.addaudithook(network_audit)
import django

django.setup()
from django.conf import settings
from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY, get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction
from django.test import Client
from django.urls import resolve
from oauth2_provider.models import Application, AccessToken, RefreshToken, Grant
from social_django.models import UserSocialAuth
from social_core.backends.google import GoogleOAuth2
from social_core.backends.twitter import TwitterOAuth
from social_core.backends.oauth import BaseOAuth2
from openedx.core.djangoapps.auth_exchange.forms import AccessTokenExchangeForm
from openedx.core.djangoapps.auth_exchange.views import DOTAccessTokenExchangeView, LoginWithAccessTokenView
from openedx.core.djangoapps.oauth_dispatch.views import GetCookie, AccessTokenExchangeView
from third_party_auth import pipeline

assert AccessTokenExchangeView.dot_view is DOTAccessTokenExchangeView
assert settings.FEATURES['ENABLE_THIRD_PARTY_AUTH']
assert 'read' in settings.OAUTH2_PROVIDER['SCOPES']
assert 'read' in dict(AccessTokenExchangeForm.base_fields['scope'].choices)
assert 'third_party_auth.middleware.ExceptionMiddleware' in settings.MIDDLEWARE
assert issubclass(GoogleOAuth2, BaseOAuth2) and not issubclass(TwitterOAuth, BaseOAuth2)
paths = {'exchange': '/oauth2/exchange_access_token/google-oauth2/',
         'cookie': '/oauth2/get_cookie/', 'login': '/oauth2/login/'}
for name, cls in [('exchange', AccessTokenExchangeView), ('cookie', GetCookie), ('login', LoginWithAccessTokenView)]:
    match = resolve(paths[name])
    assert match.func.view_class is cls, (name, match.func.view_class)
    print(json.dumps({'resolver': name, 'url_name': match.url_name, 'class': cls.__module__ + '.' + cls.__name__}))


def snapshot():
    models = [get_user_model(), Application, AccessToken, RefreshToken, Grant, UserSocialAuth]
    result = {model._meta.label: list(model.objects.order_by('pk').values_list('pk', flat=True)) for model in models}
    # Keep full session row identities/data internally; never print cookies/keys.
    result['sessions'] = dict(Session.objects.values_list('session_key', 'session_data'))
    return result


calls = Counter()
backends = set()
forbidden = []


def trace(frame, event, arg):
    if event != 'call':
        return
    filename, name = frame.f_code.co_filename, frame.f_code.co_name
    if name == 'do_auth' and '/social_core/' in filename:
        forbidden.append('do_auth')
        raise AssertionError('Input reached backend.do_auth')
    if name in {'create_access_token', 'exchange_access_token'} and '/auth_exchange/views.py' in filename:
        forbidden.append(name)
        raise AssertionError('Input reached token issuance')
    if any(part in filename for part in (
        '/django/urls/resolvers.py', '/social_django/utils.py', '/auth_exchange/',
        '/oauth_dispatch/adapters/', '/oauth_dispatch/views.py', '/django/contrib/sessions/middleware.py',
        '/third_party_auth/middleware.py', '/social_core/backends/base.py',
        '/safe_sessions/middleware.py', '/cache_toolbox/middleware.py',
    )):
        calls[filename.split('/site-packages/')[-1].split('/platform-source/')[-1] + ':' + name] += 1
    if name == '__init__' and '/social_core/backends/base.py' in filename:
        backends.add(type(frame.f_locals['self']).__module__ + '.' + type(frame.f_locals['self']).__name__)


baseline = snapshot()
with transaction.atomic():
    # Existing ordinary user is read only; no new user or authentication needed.
    owner = get_user_model().objects.filter(is_active=True, is_staff=False, is_superuser=False).first()
    assert owner is not None
    import secrets
    suffix = secrets.token_hex(6)
    fixtures = {}
    for kind in ('public', 'confidential'):
        fixtures[kind] = Application.objects.create(
            user=owner, name='lt02-acceptance-' + suffix + '-' + kind,
            client_type=kind, authorization_grant_type=Application.GRANT_PASSWORD,
            redirect_uris='http://localhost/lt02-unused-callback',
        )
    assert fixtures['public'].client_type == Application.CLIENT_PUBLIC
    assert fixtures['confidential'].client_type == Application.CLIENT_CONFIDENTIAL
    data = {'access_token': 'nonsecret-invalid-provider-token-placeholder',
            'client_id': fixtures['public'].client_id, 'scope': 'read'}
    cases = [
        ('missing_access_token', 'post', 'google-oauth2', {k:v for k,v in data.items() if k != 'access_token'}, 400, 'invalid_request', 'access_token is required', False),
        ('missing_client_id', 'post', 'google-oauth2', {k:v for k,v in data.items() if k != 'client_id'}, 400, 'invalid_request', 'client_id is required', False),
        ('nonexistent_client', 'post', 'google-oauth2', dict(data, client_id='lt02-absent-' + suffix), 400, 'invalid_client', 'lt02-absent-' + suffix + ' is not a valid client_id', True),
        ('confidential_client', 'post', 'google-oauth2', dict(data, client_id=fixtures['confidential'].client_id), 400, 'invalid_client', fixtures['confidential'].client_id + ' is not a public client', True),
        ('invalid_scope', 'post', 'google-oauth2', dict(data, scope='lt02:never-configured'), 400, 'invalid_request', "'lt02:never-configured' is not a valid scope.", False),
        ('unsupported_oauth1_backend', 'post', 'twitter', data, 400, 'invalid_request', 'twitter is not a supported provider', False),
        ('missing_backend', 'post', 'lt02-no-installed-backend', data, 404, None, None, False),
        ('get_method', 'get', 'google-oauth2', data, 400, 'invalid_request', 'Only POST requests allowed.', False),
        ('put_method', 'put', 'google-oauth2', data, 405, None, None, False),
    ]
    for label, method, backend, payload, status, error, description, anonymous_mark in cases:
        with transaction.atomic():
            before = snapshot()
            calls.clear()
            backends.clear()
            net_start = len(network)
            client = Client(enforce_csrf_checks=True, HTTP_HOST=settings.LMS_BASE)
            sys.setprofile(trace)
            try:
                response = getattr(client, method)('/oauth2/exchange_access_token/' + backend + '/', payload)
            finally:
                sys.setprofile(None)
            assert response.status_code == status, (label, response.status_code)
            if error:
                body = response.json()
                assert body.get('error') == error, (label, body.get('error'))
                assert body.get('error_description') == description, (label, 'description mismatch')
                assert 'access_token' not in body and 'refresh_token' not in body
            elif status == 405:
                assert response.json()['detail'] == 'Method "PUT" not allowed.'
            assert not response.wsgi_request.user.is_authenticated, (label, 'authenticated request')
            after = snapshot()
            assert {k:v for k,v in before.items() if k != 'sessions'} == {k:v for k,v in after.items() if k != 'sessions'}, (label, 'model identities changed')
            assert all(after['sessions'].get(k) == v for k,v in before['sessions'].items()), (label, 'existing session changed')
            new_keys = set(after['sessions']) - set(before['sessions'])
            new_sessions = [Session.objects.get(session_key=k).get_decoded() for k in new_keys]
            for session in new_sessions + [dict(response.wsgi_request.session)]:
                assert not {SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY}.intersection(session), (label, 'authenticated session')
            # Other production middleware can create anonymous session rows,
            # even when form validation exits before the pipeline marker.
            request_session = dict(response.wsgi_request.session)
            assert (request_session.get(pipeline.AUTH_ENTRY_KEY) == pipeline.AUTH_ENTRY_LOGIN_API) == anonymous_mark, (label, 'pipeline marker')
            if anonymous_mark:
                assert new_sessions and all(s.get(pipeline.AUTH_ENTRY_KEY) == pipeline.AUTH_ENTRY_LOGIN_API for s in new_sessions)
            assert any('resolvers.py:resolve' in key for key in calls), label
            assert any('safe_sessions/middleware.py:process_request' in key for key in calls), label
            assert any('social_django/utils.py:wrapper' in key for key in calls), label
            if backend != 'lt02-no-installed-backend':
                assert backends, (label, 'backend not instantiated')
            if method == 'post' and backend != 'lt02-no-installed-backend':
                assert any('/auth_exchange/views.py:post' in k for k in calls), label
                assert any('/auth_exchange/forms.py:clean' in k for k in calls), label
            if label in {'nonexistent_client', 'confidential_client'}:
                assert any('/adapters/dot.py:get_client' in k for k in calls), (label, 'adapter not reached')
            print(json.dumps({'case': label, 'status': status, 'error': error,
                'exact_description_asserted': description is not None,
                'role': 'anonymous', 'scope': payload['scope'],
                'model_identities_unchanged': True, 'existing_sessions_unchanged': True,
                'new_anonymous_sessions': len(new_sessions), 'authenticated_sessions_added': 0,
                'anonymous_session_fields': [sorted(s) for s in new_sessions],
                'auth_entry_login_api_marker': anonymous_mark,
                'backend_classes': sorted(backends), 'do_auth_calls': 0,
                'network_events': network[net_start:], 'call_trace': dict(sorted(calls.items()))}, sort_keys=True))
            transaction.set_rollback(True)
    transaction.set_rollback(True)
assert snapshot() == baseline, 'Outer rollback did not restore fixture/session identities'
assert not forbidden
print(json.dumps({'result': 'PASS', 'cases': len(cases), 'fixtures_and_sessions_rolled_back': True,
    'network_policy': 'Only mysql:3306, memcached:11211 and loopback statsd UDP8125 permitted; other DNS/connect/sendto raises',
    'network_events': network, 'external_provider_calls': 0,
    'settings_module': settings.SETTINGS_MODULE, 'python': sys.version, 'django': django.get_version(), 'middleware': settings.MIDDLEWARE,
    'authentication_backends': settings.AUTHENTICATION_BACKENDS}, sort_keys=True))
