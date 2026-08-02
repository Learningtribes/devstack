# -*- coding: utf-8 -*-
"""Provision, reset, and verify the disposable enrollment browser fixture."""
from __future__ import absolute_import, division, print_function, unicode_literals

import hashlib
import json
import os
import sys
from datetime import datetime

import django
import pytz

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.contrib.sites.models import Site  # noqa: E402
from completion.models import BlockCompletion  # noqa: E402
from opaque_keys.edx.keys import CourseKey  # noqa: E402
from six import text_type  # noqa: E402

from course_modes.models import CourseMode  # noqa: E402
from courseware.courses import get_course_with_access  # noqa: E402
from courseware.models import StudentModule  # noqa: E402
from lms.djangoapps.grades.models import PersistentCourseGrade, PersistentCourseProgress  # noqa: E402
from openedx.core.djangoapps.content.block_structure.api import clear_course_from_cache  # noqa: E402
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview  # noqa: E402
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration  # noqa: E402
from student.models import CourseEnrollment, EnrollmentOrigin, Registration, UserProfile  # noqa: E402
from xmodule.contentstore.content import StaticContent  # noqa: E402
from xmodule.contentstore.django import contentstore  # noqa: E402
from xmodule.course_module import COURSE_RELEASED_STATUS  # noqa: E402
from xmodule.modulestore import ModuleStoreEnum  # noqa: E402
from xmodule.modulestore.django import modulestore  # noqa: E402
from xmodule.modulestore.exceptions import DuplicateCourseError, ItemNotFoundError  # noqa: E402


MARKER = 'P1B_ENROLLMENT_CONTENT_OK'
DISPLAY_NAME = 'P1-B Enrollment Course View'
COURSE_START = datetime(2026, 8, 1, tzinfo=pytz.UTC)
COURSE_END = datetime(2027, 8, 1, tzinfo=pytz.UTC)
BLOCKS = (
    ('chapter', 'enrollment_section', 'Enrollment Section'),
    ('sequential', 'enrollment_subsection', 'Enrollment Subsection'),
    ('vertical', 'enrollment_unit', 'Enrollment Unit'),
    ('html', 'enrollment_html', 'Enrollment Content'),
)
RUNTIME_FIXTURES = {
    'py36': {
        'username': 'qaenroll_py36',
        'email': 'qaenroll_py36@example.com',
        'author': 'qaenroll_author_py36',
        'author_email': 'qaenroll_author_py36@example.com',
        'course_key': 'course-v1:QA+EnrollmentView+Py36',
        'namespace': 'py36_r1_p1b_enrollment_view_py36',
        'site_domain': 'localhost:18133',
        'image_name': 'p1b_enrollment_view_py36.jpg',
    },
    'py27': {
        'username': 'qaenroll_py27',
        'email': 'qaenroll_py27@example.com',
        'author': 'qaenroll_author_py27',
        'author_email': 'qaenroll_author_py27@example.com',
        'course_key': 'course-v1:QA+EnrollmentView+Py27',
        'namespace': 'py36_r1_p1b_enrollment_view_py27',
        'site_domain': 'localhost:18134',
        'image_name': 'p1b_enrollment_view_py27.jpg',
    },
}


def _fixture():
    runtime = os.environ.get('PY36_R1_ENROLLMENT_RUNTIME')
    if runtime not in RUNTIME_FIXTURES:
        raise RuntimeError('PY36_R1_ENROLLMENT_RUNTIME must be py36 or py27')
    fixture = dict(RUNTIME_FIXTURES[runtime])
    fixture['runtime'] = runtime
    environment_values = {
        'username': 'PY36_R1_ENROLLMENT_USERNAME',
        'email': 'PY36_R1_ENROLLMENT_EMAIL',
        'course_key': 'PY36_R1_ENROLLMENT_COURSE_KEY',
        'namespace': 'PY36_R1_BROWSER_NAMESPACE',
        'site_domain': 'PY36_R1_BROWSER_SITE_DOMAIN',
    }
    for key, environment_name in environment_values.items():
        value = os.environ.get(environment_name, fixture[key])
        if value != fixture[key]:
            raise RuntimeError('{} must equal the gate-owned value {!r}'.format(environment_name, fixture[key]))
        fixture[key] = value
    fixture['course_key_object'] = CourseKey.from_string(fixture['course_key'])
    return fixture


def _get_or_create_user(username, email, is_staff):
    user, _ = User.objects.get_or_create(username=username, defaults={'email': email})
    user.email = email
    user.is_active = True
    user.is_staff = is_staff
    user.is_superuser = is_staff
    user.save()
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'name': username})
    profile.name = username
    profile.save()
    Registration.objects.get_or_create(
        user=user,
        defaults={
            'activation_key': hashlib.md5(
                'p1b-enrollment-{}'.format(username).encode('utf8')
            ).hexdigest(),
        },
    )
    return user


def _get_or_create_child(store, parent_location, course_key, author_id, block_type, block_id, fields):
    location = course_key.make_usage_key(block_type, block_id)
    try:
        block = store.get_item(location)
        for field_name, value in fields.items():
            setattr(block, field_name, value)
        block = store.update_item(block, author_id)
        parent = store.get_item(parent_location)
        if not any(text_type(child) == text_type(block.location) for child in parent.children):
            parent.children = list(parent.children) + [block.location]
            store.update_item(parent, author_id)
    except ItemNotFoundError:
        block = store.create_child(
            author_id,
            parent_location,
            block_type,
            block_id=block_id,
            fields=fields,
        )
    return block


def _published_fixture(store, fixture):
    course_key = fixture['course_key_object']
    usage_keys = [course_key.make_usage_key(block_type, block_id) for block_type, block_id, _ in BLOCKS]
    with store.branch_setting(ModuleStoreEnum.Branch.published_only, course_key):
        course = store.get_course(course_key)
        blocks = [store.get_item(usage_key) for usage_key in usage_keys]
    if course is None or course.course_status != COURSE_RELEASED_STATUS:
        raise RuntimeError('published released course is missing: {}'.format(course_key))
    if MARKER not in blocks[-1].data:
        raise RuntimeError('published HTML marker is missing: {}'.format(usage_keys[-1]))
    return course, blocks


def _save_course_image(fixture):
    image_key = StaticContent.compute_location(fixture['course_key_object'], fixture['image_name'])
    stored_image = contentstore().find(image_key, throw_on_not_found=False)
    if stored_image is None or stored_image.length < 1024:
        image_path = os.path.join(
            settings.REPO_ROOT,
            'common/test/data/conditional_and_poll/static/images/course_image.jpg',
        )
        with open(image_path, 'rb') as image_file:
            contentstore().save(StaticContent(
                image_key,
                fixture['image_name'],
                'image/jpeg',
                image_file,
            ))
    stored_image = contentstore().find(image_key, throw_on_not_found=False)
    if stored_image is None or stored_image.length < 1024:
        raise RuntimeError('course image is missing or too small: {}'.format(image_key))
    return image_key, stored_image.length


def provision(fixture):
    course_key = fixture['course_key_object']
    author = _get_or_create_user(fixture['author'], fixture['author_email'], True)
    learner = _get_or_create_user(fixture['username'], fixture['email'], False)
    store = modulestore()

    with store.default_store(ModuleStoreEnum.Type.split):
        if not store.has_course(course_key):
            with store.bulk_operations(course_key):
                try:
                    store.create_course(
                        course_key.org,
                        course_key.course,
                        course_key.run,
                        author.id,
                        fields={
                            'display_name': DISPLAY_NAME,
                            'start': COURSE_START,
                            'end': COURSE_END,
                            'enrollment_start': COURSE_START,
                            'enrollment_end': COURSE_END,
                        },
                    )
                except DuplicateCourseError:
                    pass

    with store.branch_setting(ModuleStoreEnum.Branch.draft_preferred, course_key):
        with store.bulk_operations(course_key):
            course = store.get_course(course_key)
            course.display_name = DISPLAY_NAME
            course.start = COURSE_START
            course.end = COURSE_END
            course.enrollment_start = COURSE_START
            course.enrollment_end = COURSE_END
            course.invitation_only = False
            course.visible_to_staff_only = False
            course.course_status = COURSE_RELEASED_STATUS
            course.course_image = fixture['image_name']
            course = store.update_item(course, author.id)

            parent_location = course.location
            for block_type, block_id, display_name in BLOCKS:
                fields = {'display_name': display_name}
                if block_type == 'html':
                    fields['data'] = '<p>{}</p>'.format(MARKER)
                block = _get_or_create_child(
                    store,
                    parent_location,
                    course_key,
                    author.id,
                    block_type,
                    block_id,
                    fields,
                )
                parent_location = block.location
            store.publish(course.location, author.id)

    published_course, published_blocks = _published_fixture(store, fixture)
    image_key, image_length = _save_course_image(fixture)
    overview = CourseOverview.load_from_module_store(course_key)
    if overview.course_status != COURSE_RELEASED_STATUS:
        raise RuntimeError('course overview is not released: {}'.format(course_key))

    CourseMode.objects.filter(course_id=course_key).exclude(mode_slug=CourseMode.AUDIT).delete()
    CourseMode.objects.update_or_create(
        course_id=course_key,
        mode_slug=CourseMode.AUDIT,
        defaults={
            'mode_display_name': 'Audit',
            'min_price': 0,
            'currency': 'usd',
            'suggested_prices': '',
        },
    )

    site, _ = Site.objects.get_or_create(
        domain=fixture['site_domain'],
        defaults={'name': 'P1-B enrollment {}'.format(fixture['runtime'])},
    )
    site.name = 'P1-B enrollment {}'.format(fixture['runtime'])
    site.save()
    site_configuration, _ = SiteConfiguration.objects.get_or_create(
        site=site,
        defaults={'enabled': True, 'values': {}},
    )
    site_values = dict(site_configuration.values or {})
    site_values.update({
        'course_org_filter': course_key.org,
        'ENABLE_LAST_ACTIVITY': True,
    })
    site_configuration.enabled = True
    site_configuration.values = site_values
    site_configuration.save()

    clear_course_from_cache(course_key)
    print('PROVISION_OK {}'.format(json.dumps({
        'runtime': fixture['runtime'],
        'namespace': fixture['namespace'],
        'user_id': learner.id,
        'username': learner.username,
        'course_key': text_type(course_key),
        'published_usage_keys': [text_type(block.location) for block in published_blocks],
        'image_key': text_type(image_key),
        'image_length': image_length,
        'site_domain': fixture['site_domain'],
    }, sort_keys=True)))


def reset_and_preflight(fixture):
    course_key = fixture['course_key_object']
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    learner.is_staff = False
    learner.is_superuser = False
    learner.is_active = True
    learner.save()

    enrollment = CourseEnrollment.objects.filter(user=learner, course_id=course_key).first()
    if enrollment is not None and enrollment.is_active:
        CourseEnrollment.unenroll(learner, course_key)
    enrollment = CourseEnrollment.objects.filter(user=learner, course_id=course_key).first()
    if enrollment is not None and enrollment.completion_date is not None:
        enrollment.completion_date = None
        enrollment.save(update_fields=['completion_date'])

    StudentModule.objects.filter(student=learner, course_id=course_key).delete()
    BlockCompletion.objects.filter(user=learner, course_key=course_key).delete()
    PersistentCourseGrade.objects.filter(user_id=learner.id, course_id=course_key).delete()
    PersistentCourseProgress.objects.filter(user_id=learner.id, course_id=course_key).delete()

    if CourseEnrollment.is_enrolled(learner, course_key):
        raise RuntimeError('learner is still enrolled after exact reset')
    if enrollment is not None and enrollment.is_active:
        raise RuntimeError('retained enrollment row is still active after exact reset')
    if enrollment is not None and enrollment.completion_date is not None:
        raise RuntimeError('retained enrollment row still has a completion date')
    if StudentModule.objects.filter(student=learner, course_id=course_key).exists():
        raise RuntimeError('learner courseware state remains after exact reset')
    if BlockCompletion.objects.filter(user=learner, course_key=course_key).exists():
        raise RuntimeError('learner block completion remains after exact reset')

    store = modulestore()
    published_course, published_blocks = _published_fixture(store, fixture)
    overview = CourseOverview.load_from_module_store(course_key)
    clear_course_from_cache(course_key)
    modes = CourseMode.modes_for_course_dict(course_key)
    auto_mode = CourseMode.auto_enroll_mode(course_key, modes)
    if not CourseMode.can_auto_enroll(course_key, modes) or auto_mode != CourseMode.AUDIT:
        raise RuntimeError('course is not open for audit auto-enrollment')
    if published_course.id != course_key or overview.course_status != COURSE_RELEASED_STATUS:
        raise RuntimeError('published released course is not readable from ModuleStore')

    print('PRECONDITION_OK {}'.format(json.dumps({
        'runtime': fixture['runtime'],
        'namespace': fixture['namespace'],
        'username': learner.username,
        'course_key': text_type(course_key),
        'published_usage_keys': [text_type(block.location) for block in published_blocks],
        'is_enrolled': False,
        'retained_row_active': enrollment.is_active if enrollment is not None else None,
        'completion_date': enrollment.completion_date if enrollment is not None else None,
        'courseware_state_count': 0,
        'block_completion_count': 0,
        'auto_enroll_mode': auto_mode,
        'course_status': overview.course_status,
        'site_domain': fixture['site_domain'],
    }, sort_keys=True)))


def postflight(fixture):
    course_key = fixture['course_key_object']
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    enrollment = CourseEnrollment.objects.get(user=learner, course_id=course_key)
    if not enrollment.is_active or enrollment.mode != CourseMode.AUDIT:
        raise RuntimeError('active audit enrollment is missing')
    if enrollment.origin != EnrollmentOrigin.SELF:
        raise RuntimeError('enrollment origin is not SELF: {!r}'.format(enrollment.origin))
    published_course, published_blocks = _published_fixture(modulestore(), fixture)
    accessible = get_course_with_access(learner, 'load', course_key)
    if accessible.id != published_course.id:
        raise RuntimeError('enrolled learner cannot read the published course')

    print('POSTCONDITION_OK {}'.format(json.dumps({
        'runtime': fixture['runtime'],
        'namespace': fixture['namespace'],
        'username': learner.username,
        'course_key': text_type(course_key),
        'is_active': enrollment.is_active,
        'mode': enrollment.mode,
        'origin': enrollment.origin,
        'published_unit': text_type(published_blocks[2].location),
        'marker': MARKER,
    }, sort_keys=True)))


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('provision', 'reset', 'postflight'):
        raise SystemExit('usage: {} {{provision|reset|postflight}}'.format(sys.argv[0]))
    fixture = _fixture()
    actions = {
        'provision': provision,
        'reset': reset_and_preflight,
        'postflight': postflight,
    }
    actions[sys.argv[1]](fixture)


if __name__ == '__main__':
    main()
