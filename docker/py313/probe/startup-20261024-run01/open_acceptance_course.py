"""Move only the dedicated local acceptance course into its published window."""
import sys
from datetime import timedelta

sys.path.insert(0, '/edx/app/edxapp/edx-platform')
sys.path.insert(0, '/edx/app/edxapp/edx-platform/common/djangoapps')

import django

django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from opaque_keys.edx.keys import CourseKey

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.django import modulestore


course_key = CourseKey.from_string('course-v1:PY313+RuntimeChrome26+2026')
store = modulestore()
course = store.get_course(course_key)
previous_start = course.start
course.start = timezone.now() - timedelta(days=1)
store.update_item(course, get_user_model().objects.get(username='edx').id)
updated = store.get_course(course_key)
assert updated.start <= timezone.now()
user = get_user_model().objects.get(username='edx')
updated.course_status = 'released'
store.update_item(updated, user.id)
CourseOverview.load_from_module_store(course_key)
overview = CourseOverview.get_from_id(course_key)
assert overview.course_status == 'released', overview.course_status
print('Acceptance course is published and open; previously_future:', bool(previous_start and previous_start > timezone.now()))
