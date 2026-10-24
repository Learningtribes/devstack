"""Enroll the dedicated local learner in the published acceptance course."""
import json
from pathlib import Path
import sys

sys.path.insert(0, '/edx/app/edxapp/edx-platform')
sys.path.insert(0, '/edx/app/edxapp/edx-platform/common/djangoapps')

import django

django.setup()

from django.contrib.auth import get_user_model
from opaque_keys.edx.keys import CourseKey
from student.models import CourseEnrollment


credentials = json.loads(Path('/startup/.acceptance-credentials.json').read_text())
learner = get_user_model().objects.get(username=credentials['learner']['username'])
course_key = CourseKey.from_string('course-v1:PY313+RuntimeChrome26+2026')
was_enrolled = CourseEnrollment.is_enrolled(learner, course_key)
enrollment = CourseEnrollment.enroll(learner, course_key)
assert enrollment.is_active
print('Acceptance learner enrollment active; already_enrolled:', was_enrolled)
