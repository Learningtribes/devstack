# -*- coding: utf-8 -*-
"""Provision the disposable dashboard fixture for the active LMS runtime."""
from __future__ import absolute_import, division, print_function, unicode_literals

import os
from datetime import timedelta

import django

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.contrib.sites.models import Site  # noqa: E402
from django.utils import timezone  # noqa: E402
from opaque_keys.edx.keys import CourseKey  # noqa: E402

from completion.models import BlockCompletion  # noqa: E402
from courseware.courses import get_course_with_access  # noqa: E402
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview  # noqa: E402
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration  # noqa: E402
from student.models import CourseEnrollment  # noqa: E402
from xmodule.contentstore.content import StaticContent  # noqa: E402
from xmodule.contentstore.django import contentstore  # noqa: E402
from xmodule.course_module import COURSE_RELEASED_STATUS  # noqa: E402
from xmodule.modulestore import ModuleStoreEnum  # noqa: E402
from xmodule.modulestore.django import modulestore  # noqa: E402
from xmodule.modulestore.exceptions import DuplicateCourseError  # noqa: E402


COURSE_KEY = CourseKey.from_string('course-v1:QA+Acceptance+Test')
BROWSER_SITE_DOMAIN = os.environ.get('PY36_R1_BROWSER_SITE_DOMAIN')
if not BROWSER_SITE_DOMAIN:
    raise RuntimeError('PY36_R1_BROWSER_SITE_DOMAIN is required')

staff = User.objects.get(email='staff@example.com')
learner = User.objects.get(username='qacert')
store = modulestore()

try:
    with store.default_store(ModuleStoreEnum.Type.split):
        store.create_course(
            COURSE_KEY.org,
            COURSE_KEY.course,
            COURSE_KEY.run,
            staff.id,
            fields={
                'display_name': 'QA Acceptance Test',
                'start': timezone.now() - timedelta(days=1),
            },
        )
except DuplicateCourseError:
    pass

with store.branch_setting(ModuleStoreEnum.Branch.draft_preferred, COURSE_KEY):
    course = store.get_course(COURSE_KEY)
    course.course_status = COURSE_RELEASED_STATUS
    if os.environ.get('PY36_R1_BROWSER_NAMESPACE'):
        course.course_image = 'p1b_dashboard_course_image.jpg'
    course = store.update_item(course, staff.id)
    store.publish(course.location, staff.id)

CourseEnrollment.enroll(learner, COURSE_KEY)
with store.branch_setting(ModuleStoreEnum.Branch.published_only, COURSE_KEY):
    published_course = store.get_course(COURSE_KEY)
if published_course is None:
    raise RuntimeError('published course is missing: {}'.format(COURSE_KEY))
if published_course.course_status != COURSE_RELEASED_STATUS:
    raise RuntimeError('published course is not released: {}'.format(COURSE_KEY))

course_image_key = StaticContent.compute_location(COURSE_KEY, published_course.course_image)
stored_image = contentstore().find(course_image_key, throw_on_not_found=False)
if stored_image is None or stored_image.length < 1024:
    image_path = os.path.join(
        settings.REPO_ROOT,
        'common/test/data/conditional_and_poll/static/images/course_image.jpg',
    )
    with open(image_path, 'rb') as image_file:
        contentstore().save(StaticContent(
            course_image_key,
            published_course.course_image,
            'image/jpeg',
            image_file,
        ))
if contentstore().find(course_image_key, throw_on_not_found=False) is None:
    raise RuntimeError('course image is missing: {}'.format(course_image_key))

course_overview = CourseOverview.load_from_module_store(COURSE_KEY)
if course_overview.course_status != COURSE_RELEASED_STATUS:
    raise RuntimeError('course overview is not released: {}'.format(COURSE_KEY))

BlockCompletion.objects.submit_completion(
    user=learner,
    course_key=COURSE_KEY,
    block_key=published_course.location,
    completion=1.0,
)

site, _ = Site.objects.get_or_create(
    domain=BROWSER_SITE_DOMAIN,
    defaults={'name': 'P1-B disposable browser service'},
)
site_configuration, _ = SiteConfiguration.objects.get_or_create(
    site=site,
    defaults={'enabled': True, 'values': {}},
)
site_values = dict(site_configuration.values or {})
site_values.update({
    'course_org_filter': COURSE_KEY.org,
    'ENABLE_LAST_ACTIVITY': True,
})
site_configuration.enabled = True
site_configuration.values = site_values
site_configuration.save()

accessible_course = get_course_with_access(learner, 'load', COURSE_KEY)
print('PROVISION_OK user_id={} course={} site={}'.format(
    learner.id,
    accessible_course.id,
    BROWSER_SITE_DOMAIN,
))
