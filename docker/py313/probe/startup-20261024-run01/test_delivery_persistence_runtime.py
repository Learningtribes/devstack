"""Snapshot and verify the run-scoped course, GridFS files and SCORM state."""
import hashlib
import json
import os
from pathlib import Path

from django.contrib.auth import get_user_model
from courseware.models import StudentModule
from completion.models import BlockCompletion
from student.models import CourseEnrollment
from opaque_keys.edx.keys import AssetKey, UsageKey
from xmodule.contentstore.django import contentstore
from xmodule.modulestore.django import modulestore

from acceptance_context import course_key

PHASE = globals().get('PHASE')
assert PHASE in {'before', 'after'}, 'Use the before/after wrapper for an explicit persistence phase'
root = Path('/runtime')
baseline_path = root / 'delivery-persistence-baseline.json'
credentials = json.loads(Path('/startup/.acceptance-credentials.json').read_text())
scorm = json.loads((root / 'scorm-acceptance-latest.json').read_text())
assets = json.loads((root / 'gridfs-acceptance-latest.json').read_text())
course_key_value = course_key()
assert str(course_key_value) == scorm['course']
assert credentials['run_id'] == os.environ['PY313_REPLAY_ID']
store = modulestore()
course = store.get_course(course_key_value)
assert course.course_status == 'released'
usage = UsageKey.from_string(scorm['usage'])
assert usage.course_key == course_key_value
scorm_block = store.get_item(usage)
assert scorm_block.scorm_pkg == scorm['launch']


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def current_state():
    learner_data = [credentials['learner'], credentials['learner2']]
    learner_state = []
    for index, values in enumerate(learner_data):
        user = get_user_model().objects.get(username=values['username'])
        assert not user.is_staff and not user.is_superuser
        assert CourseEnrollment.is_enrolled(user, course_key_value)
        state = StudentModule.objects.get(student=user, module_state_key=usage)
        marker = scorm['markers'][index]
        assert marker in state.state
        completion = BlockCompletion.objects.get(user=user, block_key=usage)
        assert completion.completion == 1
        learner_state.append({
            'username': user.username,
            'state_sha256': sha256(state.state.encode()),
            'grade': state.grade,
            'max_grade': state.max_grade,
            'completion': completion.completion,
        })

    content = contentstore()
    file_state = []
    for asset in assets['assets']:
        stored = content.find(AssetKey.from_string(asset['usage']))
        data = stored.data
        assert sha256(data) == asset['sha256']
        file_state.append({'usage': asset['usage'], 'name': stored.name,
                           'content_type': stored.content_type, 'sha256': sha256(data)})
    file_state.extend([
        {'name': 'scorm-launch', 'sha256': sha256(scorm_block.fs.readbytes(scorm_block.scorm_pkg))},
        {'name': 'scorm-archive', 'sha256': sha256(scorm_block.fs.readbytes(scorm_block.scorm_pkg.split('/')[0] + '.zip'))},
    ])
    return {
        'course': str(course_key_value),
        'course_title': course.display_name,
        'course_status': course.course_status,
        'course_blocks': sorted(str(item.location) for item in store.get_items(course_key_value)),
        'learners': learner_state,
        'files': sorted(file_state, key=lambda row: row['name']),
    }


actual = current_state()
if PHASE == 'before':
    descriptor = os.open(baseline_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        output.write(json.dumps(actual, indent=2, sort_keys=True) + '\n')
    print('PASS captured course, Mongo/GridFS, SCORM launch and two learner completion states before restart')
else:
    expected = json.loads(baseline_path.read_text())
    assert actual == expected, [key for key in actual if actual[key] != expected.get(key)]
    print('PASS unchanged course, Mongo/GridFS, SCORM launch and two learner completion states after restart')
