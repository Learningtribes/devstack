"""Verify real local JWT access tokens and the public JWKS contract."""
import json
import secrets

import django
import jwt
from cryptography.hazmat.primitives import serialization
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client

django.setup()

from jwt.algorithms import RSAAlgorithm
from oauth2_provider.models import Application
from openedx.core.djangoapps.oauth_dispatch.models import ApplicationAccess

client = Client(HTTP_HOST='localhost:18000')

with transaction.atomic():
    suffix = secrets.token_hex(5)
    password = secrets.token_urlsafe(32)
    user = get_user_model().objects.create_user(
        username='dot-jwt-' + suffix,
        email=suffix + '@example.test',
        password=password,
    )
    client_secret = secrets.token_urlsafe(32)
    application = Application.objects.create(
        user=user,
        name='jwt-runtime-' + suffix,
        client_type=Application.CLIENT_CONFIDENTIAL,
        client_secret=client_secret,
        authorization_grant_type=Application.GRANT_PASSWORD,
    )
    ApplicationAccess.objects.create(application=application, scopes=['email', 'profile'])
    response = client.post('/oauth2/access_token', {
        'client_id': application.client_id,
        'client_secret': client_secret,
        'grant_type': 'password',
        'username': user.username,
        'password': password,
        # The local DOT scope backend exposes platform scopes; openid is
        # advertised by provider-info but is not an application scope.
        'scope': 'profile email',
        'token_type': 'jwt',
    })
    assert response.status_code == 200, response.content
    body = response.json()
    assert body['token_type'] == 'JWT'
    claims = jwt.decode(
        body['access_token'],
        # Local DEFAULT_JWT_ISSUER signs normal JWTs with the protected
        # runtime SECRET_KEY; DOT client_secret authenticates the grant.
        settings.DEFAULT_JWT_ISSUER['SECRET_KEY'],
        algorithms=['HS256'],
        audience='py313-local-lms',
        issuer='http://localhost:18000/oauth2',
    )
    assert claims['preferred_username'] == user.username
    assert claims['email'] == user.email
    assert claims['name'] is None

    provider = client.get('/oauth2/.well-known/openid-configuration')
    assert provider.status_code == 200
    provider_data = provider.json()
    assert provider_data['issuer'] == 'http://localhost:18000/oauth2'
    assert provider_data['jwks_uri'].endswith('/oauth2/jwks.json')

    jwks = client.get('/oauth2/jwks.json')
    assert jwks.status_code == 200
    keys = jwks.json()['keys']
    assert len(keys) == 1 and keys[0]['alg'] == 'RS512'
    public_key = RSAAlgorithm.from_jwk(json.dumps(keys[0]))
    private_key = serialization.load_pem_private_key(
        settings.JWT_PRIVATE_SIGNING_KEY.encode('utf-8'), password=None,
    )
    probe = jwt.encode(
        {'sub': 'jwks-probe', 'iss': provider_data['issuer'], 'aud': 'py313-local-lms'},
        private_key,
        algorithm='RS512',
        headers={'kid': keys[0]['kid']},
    )
    verified = jwt.decode(
        probe,
        public_key,
        algorithms=['RS512'],
        audience='py313-local-lms',
        issuer=provider_data['issuer'],
    )
    assert verified['sub'] == 'jwks-probe'
    transaction.set_rollback(True)

print('PASS: provider-info issuer, HS256 JWT access-token claims, and RSA JWKS signature verification')
