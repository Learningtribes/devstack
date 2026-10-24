"""Real SCORM HTTP upload, ordinary learner commits and durable isolation."""
import io,json,secrets,os
from pathlib import Path
import django,requests
from PIL import Image

django.setup()
from django.contrib.auth import get_user_model
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore
from student.models import CourseEnrollment,UserProfile
from completion.models import BlockCompletion
from courseware.models import StudentModule

values=json.loads(Path('/startup/.acceptance-credentials.json').read_text())
course=CourseKey.from_string(os.environ.get('PY313_ACCEPTANCE_COURSE_ID', 'course-v1:PY313+DiscussionRun03+2026'))
store=modulestore(); users=get_user_model(); staff=users.objects.get(username=values['staff']['username'])
assert staff.username=='py313_staff'
# New deterministic component; prior components/completion records stay untouched.
parent=store.get_course(course)
suffix=secrets.token_hex(4)
for category in ['chapter','sequential','vertical','scormxblock']:
 ident='acceptance_run03_'+suffix+'_'+category
 hits=[x for x in store.get_items(course) if x.location.block_id==ident]
 block=hits[0] if hits else store.create_child(staff.id,parent.location,category,block_id=ident,fields={'display_name':'SCORM learner isolation '+category})
 parent=block
usage=block.location
print('retained component',str(usage),flush=True)

def login(role,system='lms',credentials=None):
 v=credentials or values.get(role); base='http://localhost:'+('18010' if system=='cms' else '18000'); s=requests.Session()
 s.get(base+('/signin' if system=='cms' else '/login'))
 if role!='anonymous':
  r=s.post(base+'/login_ajax',data={'email':v['email'],'password':v['password']},headers={'X-CSRFToken':s.cookies.get('csrftoken',''),'Referer':base+'/'})
  assert r.status_code==200 and r.json().get('success'),(role,'login',r.status_code)
 return s,base

def post(s,base,path,**kwargs):
 return s.post(base+path,headers={'X-CSRFToken':s.cookies.get('csrftoken',''),'Referer':base+'/'},allow_redirects=False,**kwargs)

upload=f'/xblock/{usage}/handler/studio_upload_files'
fixture=Path('/startup/fixtures/py313-scorm12.zip').read_bytes()
# Exact routed upload endpoint and refusal before persistence.
for role in ['anonymous','learner','other_org']:
 s,base=login(role,'cms'); before=store.get_item(usage).scorm_pkg
 r=post(s,base,upload,files={'scorm_pkg':('py313-scorm12.zip',fixture,'application/zip')})
 print('upload boundary',role,r.status_code,flush=True)
 assert r.status_code in ([302,403] if role=='anonymous' else [403])
 assert store.get_item(usage).scorm_pkg==before
s,base=login('staff','cms')
r=post(s,base,upload,files={'scorm_pkg':('py313-scorm12.zip',fixture,'application/zip')})
print('course staff upload',r.status_code,flush=True)
assert r.status_code==200 and r.json()['status']=='success'
block=store.get_item(usage)
assert block.fs.exists(block.scorm_pkg) and block.fs.exists(block.scorm_pkg.split('/')[0]+'.zip')
assert b'LMSInitialize' in block.fs.readbytes(block.scorm_pkg)
# File image candidates are real multipart bytes, not field metadata.
png=io.BytesIO();Image.new('RGB',(8,8),'blue').save(png,format='PNG')
r=post(s,base,upload,files=[('cover_images[]',('run03-cover.png',png.getvalue(),'image/png'))])
print('cover candidate upload',r.status_code,flush=True)
assert r.status_code==200
block=store.get_item(usage);assert block.cover_images
candidate=block.cover_images[-1]
r=post(s,base,upload,data={'cover_image':candidate});assert r.status_code==200
block=store.get_item(usage);assert block.cover_image==candidate
print('File stored launch/zip/candidate selection',block.scorm_pkg,flush=True)
store.publish(usage.replace(block_type='vertical',block_id='acceptance_run03_'+suffix+'_vertical'),staff.id)
# A separate ordinary local learner allows fresh isolation checks.
path=Path('/startup/.scorm-isolation-credentials.json')
if path.exists(): second=json.loads(path.read_text())
else:
 second={'username':'py313_scorm_isolation','email':'py313-scorm-isolation@example.test','password':secrets.token_urlsafe(32)}
 u=users.objects.create_user(**second);UserProfile.objects.create(user=u,name='SCORM isolation learner')
 path.write_text(json.dumps(second));path.chmod(0o600)
u=users.objects.filter(username=second['username']).first()
if u is None:
 u=users.objects.create_user(**second);UserProfile.objects.create(user=u,name='SCORM isolation learner')
assert u.check_password(second['password'])
assert not u.is_staff and not u.is_superuser
CourseEnrollment.enroll(u,course)
learner=users.objects.get(username=values['learner']['username']);assert not learner.is_staff and not learner.is_superuser
CourseEnrollment.enroll(learner,course)
basepath=f'/courses/{course}/xblock/{usage}/handler/'
meta={'package_version':block.scorm_pkg_version,'package_date':block.scorm_pkg_modified.isoformat()}

def call(client,base,name,payload):
 r=post(client,base,basepath+name,json={**meta,**payload})
 print('handler',name,r.status_code,flush=True)
 assert r.status_code==200,(name,r.status_code,r.text[:160])
 return r.json()

s,base=login('learner')
t,b=login('second',credentials=second)
a=call(s,base,'scorm_get_value',{'name':'cmi.suspend_data'})['value']
z=call(t,b,'scorm_get_value',{'name':'cmi.suspend_data'})['value']
assert not a and not z,'Fresh component must begin without learner runtime state'
assert not BlockCompletion.objects.filter(user=learner,block_key=usage).exists()
call(s,base,'scorm_commit',{'cmi.suspend_data':'run03-primary-commit','cmi.core.lesson_status':'completed','cmi.core.score.raw':'91','cmi.core.score.max':'100'})
assert call(s,base,'scorm_get_value',{'name':'cmi.suspend_data'})['value']=='run03-primary-commit'
assert call(t,b,'scorm_get_value',{'name':'cmi.suspend_data'})['value']==''
assert BlockCompletion.objects.get(user=learner,block_key=usage).completion==1
assert not BlockCompletion.objects.filter(user=u,block_key=usage).exists()
call(t,b,'scorm_enforce_commit',{'cmi.suspend_data':'run03-secondary-enforce','cmi.core.lesson_status':'completed','cmi.core.score.raw':'73','cmi.core.score.max':'100'})
assert call(t,b,'scorm_get_value',{'name':'cmi.suspend_data'})['value']=='run03-secondary-enforce'
assert call(s,base,'scorm_get_value',{'name':'cmi.suspend_data'})['value']=='run03-primary-commit'
assert BlockCompletion.objects.get(user=u,block_key=usage).completion==1
for user,marker in [(learner,'run03-primary-commit'),(u,'run03-secondary-enforce')]:
 state=StudentModule.objects.get(student=user,module_state_key=usage)
 assert marker in state.state
 print('durable ordinary learner state/completion',user.id,marker,flush=True)
for role in ['anonymous','other_org']:
 x,y=login(role);r=post(x,y,basepath+'scorm_commit',json={**meta,'cmi.suspend_data':'denied'})
 print('LMS commit denied',role,r.status_code,flush=True)
 assert r.status_code in (302,403,404)
Path('/runtime/scorm-acceptance-latest.json').write_text(json.dumps({'usage':str(usage),'course':str(course),'learners':[learner.id,u.id],'launch':block.scorm_pkg}))
print('PASS real HTTP upload/storage/candidate roles; ordinary commit and enforce_commit; user state and completion isolation')
