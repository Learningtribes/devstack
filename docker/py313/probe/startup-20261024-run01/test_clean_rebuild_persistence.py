"""Snapshot actual browser-authored course and ordinary learner data around restart."""
import hashlib
import json
import os
from pathlib import Path
from django.contrib.auth import get_user_model
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore
from courseware.models import StudentModule
from completion.models import BlockCompletion
from openedx.core.djangoapps.bookmarks.models import Bookmark

key = CourseKey.from_string(os.environ['PY313_ACCEPTANCE_COURSE_ID'])
store = modulestore()
user = get_user_model().objects.get(username='py313_learner')
assert not user.is_staff and not user.is_superuser
blocks = list(store.get_items(key))
scorms = [b for b in blocks if b.category == 'scormxblock']
assert scorms
rows = {
    'user': [user.id, user.username, user.is_active, user.is_staff, user.is_superuser],
    'course': [str(key), store.get_course(key).display_name, store.get_course(key).course_status],
    'blocks': sorted((str(b.location), b.display_name) for b in blocks),
    'bookmarks': list(Bookmark.objects.filter(user=user, course_key=key).order_by('pk').values_list('id', 'usage_key')),
    'student_modules': list(StudentModule.objects.filter(student=user, course_id=key).order_by('pk').values('id', 'module_state_key', 'state', 'grade', 'max_grade')),
    'completion': list(BlockCompletion.objects.filter(user=user, context_key=key).order_by('pk').values('id', 'block_key', 'completion')),
    'files': {str(b.location): {name: hashlib.sha256(b.fs.readbytes(name)).hexdigest() for name in (b.scorm_pkg, b.scorm_pkg.split('/')[0]+'.zip')} for b in scorms},
}
assert rows['bookmarks'] and rows['completion']
rows = json.loads(json.dumps(rows, default=str))
path = Path('/runtime/clean-rebuild-persistence-baseline.json')
if phase == 'before':
    assert not path.exists()
    path.write_text(json.dumps(rows, indent=2, sort_keys=True)); path.chmod(0o600)
else:
    expected = json.loads(path.read_text())
    assert rows == expected, [k for k in rows if rows[k] != expected[k]]
print('PASS', phase, 'browser-created course/user/bookmark/student state/completion/SCORM launch and ZIP hashes', str(key))
