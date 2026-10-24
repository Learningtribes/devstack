"""Socket regression for actual JWT issuance and signature/claim refusal."""
import json,secrets
from pathlib import Path
import django,jwt,requests

django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from oauth2_provider.models import Application
from openedx.core.djangoapps.oauth_dispatch.models import ApplicationAccess
from lms.djangoapps.certificates.models import GeneratedCertificate
from opaque_keys.edx.keys import CourseKey
v=json.loads(Path('/startup/.acceptance-credentials.json').read_text())['learner']
u=get_user_model().objects.get(username=v['username'])
suffix=secrets.token_hex(5)
key=CourseKey.from_string('course-v1:PY313+DiscussionRun03+2026')
certificate,created=GeneratedCertificate.objects.get_or_create(user=u,course_id=key,defaults={'status':'downloadable','mode':'honor','grade':'0.95'})
secret=secrets.token_urlsafe(32)
a=Application.objects.create(user=u,name='jwt-socket-'+suffix,client_type=Application.CLIENT_CONFIDENTIAL,authorization_grant_type=Application.GRANT_PASSWORD,client_secret=secret)
ApplicationAccess.objects.create(application=a,scopes=['certificates:read'])
base='http://localhost:18000'
r=requests.post(base+'/oauth2/access_token',data={'client_id':a.client_id,'client_secret':secret,'grant_type':'password','username':u.username,'password':v['password'],'scope':'certificates:read','token_type':'jwt'})
assert r.status_code==200
actual=r.json()['access_token']
claims=jwt.decode(actual,options={'verify_signature':False})
url=base+f'/api/certificates/v0/certificates/{u.username}/courses/{key}/'
def check(label,token,code):
 r=requests.get(url,headers={'Authorization':'Bearer '+token})
 print(label,'expected',code,'actual',r.status_code,flush=True)
 assert r.status_code==code
 if code==200:assert r.json()['grade']==certificate.grade
check('actual-issued-HS256',actual,200)
for label,changes in [('issuer',{'iss':'https://invalid.example.test/'}),('audience',{'aud':'invalid'}),('expiry',{'exp':1})]:
 check('constructed-'+label,jwt.encode({**claims,**changes},settings.SECRET_KEY,algorithm='HS256'),401)
check('constructed-bad-signature',jwt.encode(claims,secrets.token_urlsafe(32),algorithm='HS256'),401)
print('PASS actual HTTP JWT data and distinct negative probes; retained acceptance certificate',str(key),'app',a.pk)
