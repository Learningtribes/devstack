# -*- coding: utf-8 -*-
"""
E6 browser fixture for the private MySQL clone; run through `manage.py lms shell`.

Reproduces the R1 P1-B dashboard preconditions on the canonical localhost:18000
Site: the QA course must pass the Site's course_org_filter, and qacert must have
a BlockCompletion row. Only the private clone is written; Mongo is read-only.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import os

from completion.models import BlockCompletion
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration
from student.models import CourseEnrollment
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore

COURSE_KEY = CourseKey.from_string('course-v1:QA+Acceptance+Test')
SITE_DOMAIN = 'localhost:18000'

private_host = os.environ['PY36_R2_E6_MYSQL_HOST']
for alias, config in settings.DATABASES.items():
    if config.get('HOST') != private_host:
        raise RuntimeError('database {} is not the private clone: {}'.format(alias, config.get('HOST')))

learner = User.objects.get(username='qacert')
if not CourseEnrollment.is_enrolled(learner, COURSE_KEY):
    raise RuntimeError('qacert is not enrolled in {}'.format(COURSE_KEY))

with modulestore().branch_setting(ModuleStoreEnum.Branch.published_only, COURSE_KEY):
    course = modulestore().get_course(COURSE_KEY)
if course is None:
    raise RuntimeError('published course is missing: {}'.format(COURSE_KEY))

if BlockCompletion.get_latest_block_completed(learner, COURSE_KEY) is None:
    BlockCompletion.objects.submit_completion(
        user=learner,
        course_key=COURSE_KEY,
        block_key=course.location,
        completion=1.0,
    )

# The dashboard compares course_org_filter to one org string, so a list would
# hide every enrollment; use the same single-org value as the R1 fixture.
site_configuration = SiteConfiguration.objects.get(site=Site.objects.get(domain=SITE_DOMAIN))
values = dict(site_configuration.values or {})
previous_org_filter = values.get('course_org_filter')
values['course_org_filter'] = COURSE_KEY.org
values['ENABLE_LAST_ACTIVITY'] = True
site_configuration.enabled = True
site_configuration.values = values
site_configuration.save()

print('E6_FIXTURE_OK user_id={} course={} site={} course_org_filter={}->{} enable_last_activity={}'.format(
    learner.id,
    COURSE_KEY,
    SITE_DOMAIN,
    previous_org_filter,
    values['course_org_filter'],
    values['ENABLE_LAST_ACTIVITY'],
))
