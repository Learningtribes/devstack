"""Real DOT issuance -> JWT consumer -> certificate data; SQL fixtures roll back."""
import secrets
import django
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client

django.setup()
from oauth2_provider.models import Application
from openedx.core.djangoapps.oauth_dispatch.models import ApplicationAccess, RestrictedApplication, ApplicationOrganization
from organizations.models import Organization
from lms.djangoapps.certificates.models import GeneratedCertificate
from opaque_keys.edx.keys import CourseKey
from waffle.models import Switch

client = Client(HTTP_HOST='localhost:18000')
switch_cache = Switch(name='oauth2.enforce_jwt_scopes')
try:
    with transaction.atomic():
        suffix = secrets.token_hex(5)
        password = secrets.token_urlsafe(32)
        user = get_user_model().objects.create_user(username='jwt-api-'+suffix, email=suffix+'@example.test', password=password)
        other = get_user_model().objects.create_user(username='jwt-other-'+suffix, email='other-'+suffix+'@example.test')
        course = CourseKey.from_string('course-v1:PY313+RuntimeChrome26+2026')
        foreign = CourseKey.from_string('course-v1:OTHERORG+Runtime+2026')
        for owner in (user, other):
            for key in (course, foreign):
                GeneratedCertificate.objects.create(user=owner, course_id=key, status='downloadable', mode='honor', grade='0.95')
        secret = secrets.token_urlsafe(32)
        app = Application.objects.create(user=user, name='api-'+suffix, client_type=Application.CLIENT_CONFIDENTIAL,
            client_secret=secret, authorization_grant_type=Application.GRANT_PASSWORD)
        access = ApplicationAccess.objects.create(application=app, scopes=['certificates:read', 'profile'])
        def issue(scope):
            r = client.post('/oauth2/access_token', {'client_id':app.client_id, 'client_secret':secret,
                'grant_type':'password', 'username':user.username, 'password':password, 'scope':scope, 'token_type':'jwt'})
            assert r.status_code == 200, ('issuance', r.status_code)
            token = r.json()['access_token']
            claims = jwt.decode(token, options={'verify_signature': False})
            print('issued', {'algorithm':jwt.get_unverified_header(token)['alg'], 'issuer':claims['iss'], 'scopes':claims.get('scopes'), 'filters':claims.get('filters'), 'restricted':claims.get('is_restricted')})
            return token
        def check(label, token, owner, key, expected):
            r = client.get(f'/api/certificates/v0/certificates/{owner.username}/courses/{key}/', HTTP_AUTHORIZATION='Bearer '+token)
            print(label, 'expected', expected, 'actual', r.status_code)
            assert r.status_code == expected, (label, r.status_code, r.content[:200])
            if expected == 200:
                assert r.json()['username'] == owner.username and r.json()['grade'] == '0.95'
        normal = issue('certificates:read')
        check('normal-self-data', normal, user, course, 200)
        check('normal-other-denied', normal, other, course, 403)
        switch, _ = Switch.objects.update_or_create(name='oauth2.enforce_jwt_scopes', defaults={'active':True})
        # Waffle defers invalidation to commit; this SQL-only fixture rolls back.
        switch.flush()
        RestrictedApplication.objects.create(application=app)
        org = Organization.objects.create(name='JWT runtime '+suffix, short_name='PY313')
        ApplicationOrganization.objects.create(application=app, organization=org)
        restricted = issue('certificates:read')
        check('restricted-self-org-data', restricted, user, course, 200)
        check('restricted-cross-org-denied', restricted, user, foreign, 403)
        check('restricted-other-user-denied', restricted, other, course, 403)
        missing = issue('profile')
        check('restricted-missing-scope-denied', missing, user, course, 403)
        transaction.set_rollback(True)
finally:
    switch_cache.flush()
print('PASS real issued HS256 tokens consumed by protected API; fixture data rolled back')
