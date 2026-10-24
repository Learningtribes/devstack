"""Provision registered content plugins and enrollment on the browser-created course.

Operator configuration only: keeps staff/learner permissions unchanged. Course and
unit creation/content authoring/publication remain browser acceptance operations.
"""
from django.contrib.auth import get_user_model
from opaque_keys.edx.keys import CourseKey
from student.models import CourseEnrollment
from xblock.core import XBlock
from xmodule.modulestore.django import modulestore

key = CourseKey.from_string('course-v1:PY313+CleanRebuild28+2026')
plugins = ['scormxblock', 'pdf', 'iframe', 'externality', 'lbmdonexblock', 'ilt']
for name in plugins:
    XBlock.load_class(name)
users = get_user_model()
staff = users.objects.get(username='py313_staff')
assert staff.is_staff and not staff.is_superuser
learner = users.objects.get(username='py313_learner')
assert not learner.is_staff and not learner.is_superuser
store = modulestore()
course = store.get_course(key)
assert course.course_status == 'released'
course.advanced_modules = list(dict.fromkeys(course.advanced_modules + plugins))
store.update_item(course, staff.id)
CourseEnrollment.enroll(learner, key)
assert CourseEnrollment.is_enrolled(learner, key)
print('Operator registered advanced_modules:', course.advanced_modules)
print('Enrolled ordinary learner; roles unchanged; browser-created course retained:', key)
