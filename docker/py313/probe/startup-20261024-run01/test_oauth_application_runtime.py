"""Real MySQL + DOT bearer authentication and management view regression.

No credentials printed and no authentication mocks. Each run rolls back its rows.
This is API dispatch verification, not browser or full token-endpoint acceptance.
"""
import secrets
from datetime import timedelta
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.utils import timezone
from oauth2_provider.models import Application, AccessToken
from rest_framework.test import APIRequestFactory
from openedx.core.djangoapps.oauth_dispatch.api.views import request_user_application, request_user_application_action

factory = APIRequestFactory()
with transaction.atomic():
    suffix = secrets.token_hex(6)
    admin = User.objects.create(username='dot_admin_'+suffix,email='admin'+suffix+'@example.test',is_staff=True)
    owner = User.objects.create(username='dot_owner_'+suffix,email='owner'+suffix+'@example.test')
    inactive = User.objects.create(username='dot_inactive_'+suffix,email='inactive'+suffix+'@example.test',is_active=False)
    issuer = Application.objects.create(name='probe-issuer', user=admin,client_type=Application.CLIENT_CONFIDENTIAL,authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS)
    def bearer(user, expired=False):
        value = secrets.token_urlsafe(32)
        AccessToken.objects.create(user=user,application=issuer,token=value,scope='read write',expires=timezone.now()+timedelta(seconds=-1 if expired else 300))
        return {'HTTP_AUTHORIZATION':'Bearer '+value}
    admin_header = bearer(admin)
    def action(method, data, header=admin_header):
        return request_user_application_action(getattr(factory,method)('/oauth2/api/v0/application/',data,format='json',**header))
    assert action('post',{'email':owner.email},{}).status_code == 401
    assert action('post',{'email':owner.email},bearer(owner)).status_code == 403
    assert action('post',{'email':owner.email},bearer(admin,True)).status_code == 401
    assert action('post',{}).status_code == 400
    assert action('post',{'email':['wrong']}).status_code == 400
    assert action('post',{'email':inactive.email}).status_code == 403
    created=action('post',{'email':owner.email})
    assert created.status_code == 201
    assert created['Cache-Control'] == 'no-store'
    application=Application.objects.get(user=owner,name='API')
    assert application.client_type == Application.CLIENT_CONFIDENTIAL
    assert application.authorization_grant_type == Application.GRANT_CLIENT_CREDENTIALS
    assert application.client_secret != created.data['client_secret']
    assert check_password(created.data['client_secret'],application.client_secret)
    read=request_user_application(factory.get('/unused',**admin_header),owner.email)
    assert read.status_code == 200 and 'client_secret' not in read.data
    assert action('post',{'email':owner.email}).status_code == 409
    other=Application.objects.create(user=owner,name='unrelated',client_type=Application.CLIENT_CONFIDENTIAL,authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE)
    token=AccessToken.objects.create(user=owner,application=application,token=secrets.token_urlsafe(32),scope='read',expires=timezone.now()+timedelta(seconds=300))
    assert action('delete',{'email':owner.email}).status_code == 204
    assert not AccessToken.objects.filter(pk=token.pk).exists()
    assert Application.objects.filter(pk=other.pk).exists()
    assert action('delete',{'email':owner.email}).status_code == 404
    admin.is_active=False
    admin.save(update_fields=['is_active'])
    assert action('post',{'email':owner.email}).status_code == 401
    transaction.set_rollback(True)
print('PASS: real DOT secret hashing, bearer/role/expiry/disabled negatives, input checks, one-time secret and scoped deletion')
