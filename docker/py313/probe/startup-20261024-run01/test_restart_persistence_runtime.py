"""Run28 expanded persistence, real sessions and actual HS256 before/after restart."""
import datetime
import hashlib
import json
from pathlib import Path
import secrets
import requests
from django.contrib.auth import get_user_model
from oauth2_provider.models import Application
from openedx.core.djangoapps.oauth_dispatch.models import ApplicationAccess
from openedx.core.djangoapps.bookmarks.models import Bookmark
from courseware.models import StudentModule, XModuleUserStateSummaryField
from completion.models import BlockCompletion
from lms.djangoapps.certificates.models import GeneratedCertificate
from opaque_keys.edx.keys import CourseKey, UsageKey
from xmodule.modulestore.django import modulestore

base = 'http://localhost:18000'
course = CourseKey.from_string('course-v1:PY313+CleanRebuild28+2026')
store = modulestore()
values = json.loads(Path('/startup/.acceptance-credentials.json').read_text())
credentials = json.loads(Path('/startup/.scorm-isolation-credentials.json').read_text())
user = get_user_model().objects.get(username=credentials['username'])
learner = get_user_model().objects.get(username=values['learner']['username'])
secret_path = Path('/runtime/run36-persistence02-private.json')
public_path = Path('/runtime/run36-persistence02-baseline.json')

def digest(blob):
    return hashlib.sha256(blob).hexdigest()

def snapshot():
    result = {'users':list(get_user_model().objects.filter(pk__in=[user.pk,learner.pk]).values('id','username','is_active','is_staff','is_superuser')), 'course':store.get_course(course).display_name}
    result['bookmarks'] = list(Bookmark.objects.filter(user=learner,course_key=course).values_list('id','usage_key'))
    assert result['bookmarks'], 'Existing browser bookmark must persist'
    result['student_modules'] = list(StudentModule.objects.filter(student_id__in=[user.pk,learner.pk],course_id=course).order_by('pk').values('id','student_id','module_state_key','state','grade','max_grade'))
    result['completion'] = list(BlockCompletion.objects.filter(user_id__in=[user.pk,learner.pk],context_key=course).order_by('pk').values('id','user_id','block_key','completion'))
    ilt = UsageKey.from_string('block-v1:PY313+CleanRebuild28+2026+type@ilt+block@067328f31ae149c28d706a280981dc77')
    result['ilt'] = list(XModuleUserStateSummaryField.objects.filter(usage_id=ilt).order_by('pk').values('field_name','value'))
    scorm = store.get_item(UsageKey.from_string('block-v1:PY313+CleanRebuild28+2026+type@scormxblock+block@171e928eb7424b2182f8497a1d5da671'))
    result['scorm'] = {'launch':scorm.scorm_pkg,'sha256':digest(scorm.fs.readbytes(scorm.scorm_pkg)),'zip_sha256':digest(scorm.fs.readbytes(scorm.scorm_pkg.split('/')[0]+'.zip'))}
    pdf = store.get_item(UsageKey.from_string('block-v1:PY313+CleanRebuild28+2026+type@pdf+block@6399061df9c247c49d4233661d101ba4'))
    result['pdf'] = {'name':pdf.display_name,'url':pdf.url}
    r = session.get(pdf.url.replace('localhost:18120','localhost:18000'))
    assert r.status_code == 200
    result['pdf']['sha256'] = digest(r.content)
    assert r.content == Path('/startup/fixtures/py313-textbook.pdf').read_bytes()
    return json.loads(json.dumps(result,default=str))

if phase == 'before':
    assert not secret_path.exists() and not public_path.exists()
    session = requests.Session()
    session.get(base+'/login')
    r = session.post(base+'/login_ajax', data={'email':credentials['email'],'password':credentials['password']},headers={'X-CSRFToken':session.cookies.get('csrftoken',''),'Referer':base+'/'})
    assert r.status_code == 200 and r.json().get('success')
    assert session.get(base+'/dashboard').status_code == 200
    certificate,_ = GeneratedCertificate.objects.get_or_create(user=user,course_id=course,defaults={'status':'downloadable','mode':'honor','grade':'0.91'})
    secret = secrets.token_urlsafe(32)
    app = Application.objects.create(user=user,name='run36-persistence-'+secrets.token_hex(5),client_type=Application.CLIENT_CONFIDENTIAL,authorization_grant_type=Application.GRANT_PASSWORD,client_secret=secret)
    ApplicationAccess.objects.create(application=app,scopes=['certificates:read'])
    r = requests.post(base+'/oauth2/access_token',data={'client_id':app.client_id,'client_secret':secret,'grant_type':'password','username':user.username,'password':credentials['password'],'scope':'certificates:read','token_type':'jwt'})
    assert r.status_code == 200
    private = {'cookies':requests.utils.dict_from_cookiejar(session.cookies),'token':r.json()['access_token'],'certificate_url':base+f'/api/certificates/v0/certificates/{user.username}/courses/{course}/'}
    secret_path.write_text(json.dumps(private));secret_path.chmod(0o600)
    public_path.write_text(json.dumps(snapshot(),indent=2,sort_keys=True));public_path.chmod(0o600)
elif phase == 'refresh':
    private = json.loads(secret_path.read_text())
    session = requests.Session();session.cookies.update(private['cookies'])
    public_path = Path('/runtime/run36-persistence03-baseline.json')
    assert not public_path.exists()
    public_path.write_text(json.dumps(snapshot(),indent=2,sort_keys=True));public_path.chmod(0o600)
else:
    public_path = Path('/runtime/run36-persistence03-baseline.json')
    private = json.loads(secret_path.read_text())
    session = requests.Session();session.cookies.update(private['cookies'])
    r = session.get(base+'/dashboard',allow_redirects=False)
    assert r.status_code == 200, ('retained session',r.status_code)
    actual = snapshot(); expected = json.loads(public_path.read_text())
    assert actual == expected, [k for k in actual if actual[k] != expected[k]]
    print('PASS unchanged user/course/bookmark/student state/completion/ILT/PDF/SCORM files after scoped restart',flush=True)
private = json.loads(secret_path.read_text())
r = requests.get(private['certificate_url'],headers={'Authorization':'Bearer '+private['token']})
assert r.status_code == 200 and r.json()['grade'] == '0.91'
print('PASS '+phase+' real learner session and actual issued HS256 token accepted; token remains subject to expiry/logout rules',flush=True)
print('UTC',datetime.datetime.now(datetime.timezone.utc).isoformat(),flush=True)
