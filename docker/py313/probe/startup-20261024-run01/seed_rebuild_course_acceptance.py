"""Provision plugins, course-scoped author role and enrollment after browser authoring.

Operator configuration grants the named author course-level instructor permissions,
without Django staff/superuser access. Course and unit authoring/publication remain
browser acceptance operations.
"""
import json
import os
from pathlib import Path

from django.contrib.auth import get_user_model
from opaque_keys.edx.keys import CourseKey
from student.auth import STUDIO_RELEASE_COURSE, get_user_permissions, has_course_author_access
from student.models import CourseEnrollment
from student.roles import (
    CONTENT_EDITOR_LEVEL,
    STUDIO_ADMIN_ACCESS_GROUP,
    CourseInstructorRole,
    get_platform_role,
)
from xblock.core import XBlock
from xmodule.modulestore.django import modulestore

key = CourseKey.from_string(os.environ['PY313_ACCEPTANCE_COURSE_ID'])
plugins = ['scormxblock', 'pdf', 'iframe', 'externality', 'lbmdonexblock', 'ilt']
for name in plugins:
    XBlock.load_class(name)
users = get_user_model()
credentials = json.loads(Path('/startup/.acceptance-credentials.json').read_text())
assert credentials['run_id'] == os.environ['PY313_REPLAY_ID']
staff = users.objects.get(username=credentials['staff']['username'])
assert not staff.is_staff and not staff.is_superuser
assert staff.groups.filter(name=STUDIO_ADMIN_ACCESS_GROUP).exists()
assert get_platform_role(staff) == CONTENT_EDITOR_LEVEL
learner = users.objects.get(username=credentials['learner']['username'])
assert not learner.is_staff and not learner.is_superuser
assert not learner.groups.filter(name=STUDIO_ADMIN_ACCESS_GROUP).exists()
store = modulestore()
course = store.get_course(key)
assert course.course_status == 'released'
instructor_role = CourseInstructorRole(key)
if not instructor_role.has_user(staff):
    instructor_role.add_users(staff)
assert instructor_role.has_user(staff), 'Expected instructor role on the target course'
assert has_course_author_access(staff, key), 'Expected course-scoped author access for the named staff identity'
assert get_user_permissions(staff, key) & STUDIO_RELEASE_COURSE, 'Expected course-scoped release permission'
assert not has_course_author_access(learner, key), 'Ordinary learner unexpectedly has author access'
other_course = key.replace(course='Unrelated_' + os.environ['PY313_REPLAY_ID'])
assert not has_course_author_access(staff, other_course), 'Course author unexpectedly has author access outside the assigned course'
assert not get_user_permissions(staff, other_course) & STUDIO_RELEASE_COURSE, 'Release permission leaked to another course'
course.advanced_modules = list(dict.fromkeys(course.advanced_modules + plugins))
store.update_item(course, staff.id)
CourseEnrollment.enroll(learner, key)
assert CourseEnrollment.is_enrolled(learner, key)
print('Named course author has no Django staff or superuser privilege; authoring is verified against the target course role')
print('Operator registered advanced_modules:', course.advanced_modules)
print('Enrolled ordinary learner; roles unchanged; browser-created course retained:', key)
