"""Actual DOT password issuance over sockets -> one-use session -> logout."""
import json
from pathlib import Path
import secrets
import django
import requests

django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model, SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from oauth2_provider.models import Application, AccessToken
from openedx.core.djangoapps.oauth_dispatch.models import ApplicationAccess
from openedx.core.djangoapps.safe_sessions.middleware import SafeCookieData

values=json.loads(Path('/startup/.acceptance-credentials.json').read_text())['learner']
u=get_user_model().objects.get(username=values['username'])
assert not u.is_staff and not u.is_superuser
secret=secrets.token_urlsafe(32)
app=Application.objects.create(user=u,name='socket-cookie-'+secrets.token_hex(5),client_type=Application.CLIENT_CONFIDENTIAL,authorization_grant_type=Application.GRANT_PASSWORD,client_secret=secret)
ApplicationAccess.objects.create(application=app,scopes=['read'])
base='http://localhost:18000'
s=requests.Session()
r=s.post(base+'/oauth2/access_token',data={'client_id':app.client_id,'client_secret':secret,'grant_type':'password','username':u.username,'password':values['password'],'scope':'read'})
assert r.status_code==200, ('issue',r.status_code)
token=r.json()['access_token']
assert AccessToken.objects.filter(application=app).exists()
print('actual password issuance',r.status_code,'user',u.pk,'app',app.pk,flush=True)
header={'Authorization':'Bearer '+token}
for target in ['https://example.invalid/','//example.invalid/','javascript:alert(1)']:
 r=s.post(base+'/oauth2/get_cookie/',data={'next':target},headers=header,allow_redirects=False)
 assert r.status_code==400
 assert AccessToken.objects.filter(application=app).exists()
print('external redirect refusal 400; token retained')
r=s.post(base+'/oauth2/get_cookie/',data={'next':'/dashboard'},headers=header,allow_redirects=False)
assert r.status_code==302 and r.headers['Location']=='/dashboard',('exchange',r.status_code)
cookie=SafeCookieData.parse(s.cookies.get(settings.SESSION_COOKIE_NAME))
assert cookie.verify(u.pk)
assert int(SessionStore(cookie.session_id)[SESSION_KEY])==u.pk
assert not AccessToken.objects.filter(application=app).exists()
assert s.get(base+'/dashboard').status_code==200
print('exchange 302; signed session bound to learner; dashboard 200; access token consumed')
assert requests.post(base+'/oauth2/get_cookie/',headers=header).status_code==401
assert requests.post(base+'/oauth2/get_cookie/').status_code==401
print('replayed and missing token 401')
r=s.get(base+'/logout',params={'redirect_url':'https://example.invalid/'},allow_redirects=False)
assert r.status_code==302 and r.headers['Location']=='/'
assert SESSION_KEY not in SessionStore(cookie.session_id)
assert settings.SESSION_COOKIE_NAME+'=""' in r.headers.get('Set-Cookie','')
r=s.get(base+'/dashboard',allow_redirects=False)
assert r.status_code==302 and '/login' in r.headers['Location']
print('logout 302 internal; session invalidated; dashboard requires login')
print('PASS actual socket issuance -> exchange -> signed learner session -> logout; local app retained without plaintext secret')
