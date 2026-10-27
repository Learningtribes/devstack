"""Real SCORM HTTP upload, ordinary learner commits and durable isolation."""
import io,json,secrets,os
from pathlib import Path
import django,requests
from PIL import Image

django.setup()
from django.contrib.auth import get_user_model
from xmodule.modulestore.django import modulestore
from student.models import CourseEnrollment,UserProfile
from completion.models import BlockCompletion
from courseware.models import StudentModule

values=json.loads(Path('/startup/.acceptance-credentials.json').read_text())
from acceptance_context import course_key
from student.auth import STUDIO_RELEASE_COURSE, get_user_permissions, has_course_author_access, user_has_role
from student.roles import (
    CONTENT_EDITOR_LEVEL,
    STUDIO_ADMIN_ACCESS_GROUP,
    CourseInstructorRole,
    CourseStaffRole,
    get_platform_role,
)
course=course_key()
store=modulestore(); users=get_user_model(); staff=users.objects.get(username=values['staff']['username'])
assert values['run_id']==os.environ['PY313_REPLAY_ID']
assert not staff.is_staff and not staff.is_superuser
assert staff.groups.filter(name=STUDIO_ADMIN_ACCESS_GROUP).exists()
assert get_platform_role(staff)==CONTENT_EDITOR_LEVEL
assert CourseInstructorRole(course).has_user(staff)
assert user_has_role(staff, CourseStaffRole(course)) and has_course_author_access(staff,course)
assert get_user_permissions(staff, course) & STUDIO_RELEASE_COURSE
other_course=course.replace(course='Unrelated_'+values['run_id'])
assert not has_course_author_access(staff,other_course),'Course author unexpectedly has authoring access outside the assigned course'
assert not get_user_permissions(staff, other_course) & STUDIO_RELEASE_COURSE,'Course release permission unexpectedly crossed course boundaries'
# New deterministic component; prior components/completion records stay untouched.
parent=store.get_course(course)
suffix=secrets.token_hex(4)
vertical=None
for category in ['chapter','sequential','vertical','scormxblock']:
 ident='acceptance_'+values['run_id']+'_'+suffix+'_'+category
 hits=[x for x in store.get_items(course) if x.location.block_id==ident]
 block=hits[0] if hits else store.create_child(staff.id,parent.location,category,block_id=ident,fields={'display_name':'SCORM learner isolation '+category})
 if category=='vertical': vertical=block
 parent=block
assert vertical is not None
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
store.publish(vertical.location,staff.id)
# A second run-scoped ordinary learner is provisioned before the runtime starts.
second=values['learner2']
u=users.objects.get(username=second['username'])
UserProfile.objects.get_or_create(user=u,defaults={'name':'SCORM isolation learner'})
assert u.check_password(second['password'])
assert not u.is_staff and not u.is_superuser
assert not u.groups.filter(name=STUDIO_ADMIN_ACCESS_GROUP).exists()
CourseEnrollment.enroll(u,course)
learner=users.objects.get(username=values['learner']['username']);assert not learner.is_staff and not learner.is_superuser
assert not learner.groups.filter(name=STUDIO_ADMIN_ACCESS_GROUP).exists()
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
primary_marker=values['run_id']+'-'+suffix+'-primary-commit'
secondary_marker=values['run_id']+'-'+suffix+'-secondary-enforce'
call(s,base,'scorm_commit',{'cmi.suspend_data':primary_marker,'cmi.core.lesson_status':'completed','cmi.core.score.raw':'91','cmi.core.score.max':'100'})
assert call(s,base,'scorm_get_value',{'name':'cmi.suspend_data'})['value']==primary_marker
assert call(t,b,'scorm_get_value',{'name':'cmi.suspend_data'})['value']==''
assert BlockCompletion.objects.get(user=learner,block_key=usage).completion==1
assert not BlockCompletion.objects.filter(user=u,block_key=usage).exists()
call(t,b,'scorm_enforce_commit',{'cmi.suspend_data':secondary_marker,'cmi.core.lesson_status':'completed','cmi.core.score.raw':'73','cmi.core.score.max':'100'})
assert call(t,b,'scorm_get_value',{'name':'cmi.suspend_data'})['value']==secondary_marker
assert call(s,base,'scorm_get_value',{'name':'cmi.suspend_data'})['value']==primary_marker
assert BlockCompletion.objects.get(user=u,block_key=usage).completion==1
for user,marker in [(learner,primary_marker),(u,secondary_marker)]:
 state=StudentModule.objects.get(student=user,module_state_key=usage)
 assert marker in state.state
 print('durable ordinary learner state/completion',user.id,marker,flush=True)
for role in ['anonymous','other_org']:
 x,y=login(role);r=post(x,y,basepath+'scorm_commit',json={**meta,'cmi.suspend_data':'denied'})
 print('LMS commit denied',role,r.status_code,flush=True)
 assert r.status_code in (302,403,404)
metadata={'usage':str(usage),'course':str(course),'learners':[learner.id,u.id],
          'learner_usernames':[learner.username,u.username], 'launch':block.scorm_pkg,
          'markers':[primary_marker,secondary_marker]}
target=Path('/runtime/scorm-acceptance-latest.json')
fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as output: output.write(json.dumps(metadata,sort_keys=True)+'\n')
print('PASS real HTTP upload/storage/candidate roles; ordinary commit and enforce_commit; user state and completion isolation')
