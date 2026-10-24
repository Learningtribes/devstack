"""Resume app initialization for this run's interrupted Chrome-created course.

This does not count as browser creation acceptance. Preserve failed course data.
Execute through CMS manage.py shell, then retry a new course through the UI.
"""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import InMemoryUploadedFile
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore
from contentstore.views.course import (
    add_instructor, add_course_honor_mode, initialize_permissions,
    get_organization_by_short_name, add_organization_course,
)
from contentstore.views.assets import update_course_run_asset
from course_modes.models import CourseMode

key = CourseKey.from_string('course-v1:PY313+RuntimeChrome25+2026')
user = get_user_model().objects.get(username='edx')
course = modulestore().get_course(key)
assert course.created_by_id == user.id
image = Path('/edx/app/edxapp/edx-platform/cms/static/images/triboo_default_image.jpg')
with image.open('rb') as stream:
    upload = InMemoryUploadedFile(stream, 'images_course_image', 'images_course_image.jpg',
                                  'image/jpeg', image.stat().st_size, None)
    update_course_run_asset(key, upload)
add_instructor(key, user, user)
if not CourseMode.objects.filter(course_id=key, mode_slug='honor', currency='usd').exists():
    add_course_honor_mode(key)
initialize_permissions(key, user)
add_organization_course(get_organization_by_short_name(key.org), key)
print('Resumed application initialization', key)
