# -*- coding: utf-8 -*-
"""Provision and externally verify the isolated Studio edit/publish fixture."""
from __future__ import absolute_import, division, print_function, unicode_literals

import hashlib
from io import BytesIO
import json
import os
from datetime import datetime

import django
import pytz

django.setup()

from django.contrib.auth.models import Group, User  # noqa: E402
from django.contrib.sites.models import Site  # noqa: E402
from django.utils import timezone  # noqa: E402
from opaque_keys.edx.keys import CourseKey  # noqa: E402
from six import text_type  # noqa: E402

from course_modes.models import CourseMode  # noqa: E402
from contentstore.courseware_index import CourseAboutSearchIndexer  # noqa: E402
from openedx.core.djangoapps.content.block_structure.api import clear_course_from_cache  # noqa: E402
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview  # noqa: E402
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration  # noqa: E402
from search.tests.mock_search_engine import MockSearchEngine  # noqa: E402
from student.models import (  # noqa: E402
    CourseAccessRole,
    CourseEnrollment,
    EnrollmentOrigin,
    Registration,
    UserProfile,
)
from student.roles import CourseStaffRole, STUDIO_ADMIN_ACCESS_GROUP  # noqa: E402
from xmodule.course_module import COURSE_RELEASED_STATUS  # noqa: E402
from xmodule.contentstore.content import StaticContent  # noqa: E402
from xmodule.contentstore.django import contentstore  # noqa: E402
from xmodule.modulestore import ModuleStoreEnum  # noqa: E402
from xmodule.modulestore.django import modulestore  # noqa: E402
from xmodule.modulestore.exceptions import DuplicateCourseError, ItemNotFoundError  # noqa: E402


RUNTIME = os.environ.get('PY36_R1_STUDIO_RUNTIME')
if RUNTIME not in ('py36', 'py27'):
    raise RuntimeError('PY36_R1_STUDIO_RUNTIME must be py36 or py27')

FIXTURES = {
    'py36': {
        'author': 'qastudio_py36',
        'author_email': 'qastudio_py36@example.com',
        'learner': 'qastudiolearner_py36',
        'learner_email': 'qastudiolearner_py36@example.com',
        'course_key': 'course-v1:QA+StudioPublish+Py36',
        'site_cms': 'localhost:18141',
        'site_lms': 'localhost:18142',
        'namespace': 'py36_r1_p1b_studio_publish_py36_r1',
        'baseline': 'STUDIO_PUBLISH_BASELINE_PY36',
    },
    'py27': {
        'author': 'qastudio_py27',
        'author_email': 'qastudio_py27@example.com',
        'learner': 'qastudiolearner_py27',
        'learner_email': 'qastudiolearner_py27@example.com',
        'course_key': 'course-v1:QA+StudioPublish+Py27',
        'site_cms': 'localhost:18143',
        'site_lms': 'localhost:18144',
        'namespace': 'py36_r1_p1b_studio_publish_py27_r1',
        'baseline': 'STUDIO_PUBLISH_BASELINE_PY27',
    },
}

BLOCKS = (
    ('chapter', 'studio_publish_section', 'Studio Publish Section'),
    ('sequential', 'studio_publish_subsection', 'Studio Publish Subsection'),
    ('vertical', 'studio_publish_unit', 'Studio Publish Unit'),
    ('html', 'studio_publish_html', 'Studio Publish HTML'),
)
COURSE_START = datetime(2026, 8, 1, tzinfo=pytz.UTC)
COURSE_END = datetime(2027, 8, 1, tzinfo=pytz.UTC)


def fixture():
    result = dict(FIXTURES[RUNTIME])
    expected_namespace = result['namespace']
    for key, env_name in (
            ('author', 'PY36_R1_STUDIO_AUTHOR'),
            ('learner', 'PY36_R1_STUDIO_LEARNER'),
            ('course_key', 'PY36_R1_STUDIO_COURSE_KEY'),
            ('namespace', 'PY36_R1_STUDIO_NAMESPACE')):
        value = os.environ.get(env_name, result[key])
        if value != result[key]:
            raise RuntimeError('{} must equal {!r}'.format(env_name, result[key]))
        result[key] = value
    if result['namespace'] != expected_namespace:
        raise RuntimeError('fixture namespace changed')
    result['runtime'] = RUNTIME
    result['course_key_object'] = CourseKey.from_string(result['course_key'])
    result['usage_keys'] = {
        block_type: result['course_key_object'].make_usage_key(block_type, block_id)
        for block_type, block_id, _ in BLOCKS
    }
    result['evidence_dir'] = os.environ.get(
        'PY36_R1_STUDIO_EVIDENCE_DIR', '/edx/var/log/studio-evidence'
    )
    result['attempt'] = os.environ.get('PY36_R1_STUDIO_ATTEMPT', '0')
    result['after'] = 'STUDIO_PUBLISH_AFTER_{}_ATTEMPT_{}'.format(
        RUNTIME.upper(), result['attempt']
    )
    return result


def emit(label, payload):
    print('{} {}'.format(label, json.dumps(payload, sort_keys=True, default=text_type)))


def write_evidence(fixture_data, name, payload):
    if not os.path.isdir(fixture_data['evidence_dir']):
        os.makedirs(fixture_data['evidence_dir'])
    output = os.path.join(fixture_data['evidence_dir'], name)
    with open(output, 'w') as evidence_file:
        evidence_file.write(json.dumps(payload, sort_keys=True, indent=2, default=text_type))
    return output


def get_or_create_user(username, email, password):
    user, _ = User.objects.get_or_create(username=username, defaults={'email': email})
    user.email = email
    user.is_active = True
    user.is_staff = False
    user.is_superuser = False
    user.set_password(password)
    user.save()
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'name': username})
    profile.name = username
    profile.save()
    Registration.objects.get_or_create(
        user=user,
        defaults={'activation_key': hashlib.md5(
            ('p1b-studio-' + username).encode('utf-8')
        ).hexdigest()},
    )
    return user


def configure_identities(fixture_data):
    author = get_or_create_user(
        fixture_data['author'], fixture_data['author_email'],
        os.environ['PY36_R1_STUDIO_AUTHOR_PASSWORD'],
    )
    learner = get_or_create_user(
        fixture_data['learner'], fixture_data['learner_email'],
        os.environ['PY36_R1_STUDIO_LEARNER_PASSWORD'],
    )
    studio_admin, _ = Group.objects.get_or_create(name=STUDIO_ADMIN_ACCESS_GROUP)
    author.groups.clear()
    author.groups.add(studio_admin)
    learner.groups.clear()
    CourseAccessRole.objects.filter(user=author).delete()
    CourseAccessRole.objects.filter(user=learner).delete()
    CourseStaffRole(fixture_data['course_key_object']).add_users(author)
    return author, learner


def ensure_sites(fixture_data):
    values = {
        'course_org_filter': fixture_data['course_key_object'].org,
        'ENABLE_LAST_ACTIVITY': True,
    }
    site_ids = {}
    for service, domain in (('cms', fixture_data['site_cms']), ('lms', fixture_data['site_lms'])):
        site_id = int(os.environ['PY36_R1_STUDIO_SITE_ID_{}'.format(service.upper())])
        site, _ = Site.objects.get_or_create(
            id=site_id,
            defaults={
                'domain': domain,
                'name': 'P1-B Studio Publish {} {}'.format(fixture_data['runtime'], service),
            },
        )
        Site.objects.filter(domain=domain).exclude(id=site_id).delete()
        site.domain = domain
        site.name = 'P1-B Studio Publish {} {}'.format(fixture_data['runtime'], service)
        site.save()
        config, _ = SiteConfiguration.objects.get_or_create(
            site=site, defaults={'enabled': True, 'values': {}},
        )
        config.enabled = True
        config.values = values
        config.save()
        site_ids[service] = site.id
    return site_ids


def ensure_child(store, parent_location, course_key, author_id, block_type, block_id, fields):
    location = course_key.make_usage_key(block_type, block_id)
    try:
        block = store.get_item(location)
        for field_name, value in fields.items():
            setattr(block, field_name, value)
        block = store.update_item(block, author_id)
        parent = store.get_item(parent_location)
        if list(parent.children).count(block.location) != 1:
            parent.children = [child for child in parent.children if child != block.location]
            parent.children = list(parent.children) + [block.location]
            store.update_item(parent, author_id)
    except ItemNotFoundError:
        block = store.create_child(
            author_id, parent_location, block_type, block_id=block_id, fields=fields,
        )
    return block


def ensure_course(fixture_data, author):
    course_key = fixture_data['course_key_object']
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
                            'display_name': 'Studio Publish Browser Course',
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
            course.display_name = 'Studio Publish Browser Course'
            course.start = COURSE_START
            course.end = COURSE_END
            course.enrollment_start = COURSE_START
            course.enrollment_end = COURSE_END
            course.course_status = COURSE_RELEASED_STATUS
            course.invitation_only = False
            course.visible_to_staff_only = False
            parent_location = course.location
            for block_type, block_id, display_name in BLOCKS:
                fields = {'display_name': display_name}
                if block_type == 'html':
                    fields['data'] = '<p>{}</p>'.format(fixture_data['baseline'])
                block = ensure_child(
                    store, parent_location, course_key, author.id,
                    block_type, block_id, fields,
                )
                parent_location = block.location
            course = store.get_course(course_key)
            course.display_name = 'Studio Publish Browser Course'
            course.course_status = COURSE_RELEASED_STATUS
            course.invitation_only = False
            course.visible_to_staff_only = False
            store.update_item(course, author.id)
            course_location = course.location
    store.publish(course_location, author.id)
    image_path = os.path.join(
        os.environ.get('PY36_R1_STUDIO_ASSET_DIR', '/edx/var/edxapp/staticfiles'),
        'studio', 'images', 'studio-illustration.jpg',
    )
    if not os.path.isfile(image_path):
        raise RuntimeError('fixture course image is missing: {}'.format(image_path))
    with open(image_path, 'rb') as image_file:
        contentstore().save(StaticContent(
            StaticContent.compute_location(course_key, course.course_image),
            course.course_image,
            'image/jpeg',
            BytesIO(image_file.read()),
        ))
    CourseOverview.load_from_module_store(course_key)
    clear_course_from_cache(course_key)
    return course_location


def ensure_enrollment(fixture_data, learner):
    course_key = fixture_data['course_key_object']
    CourseMode.objects.filter(course_id=course_key).exclude(mode_slug=CourseMode.AUDIT).delete()
    CourseMode.objects.update_or_create(
        course_id=course_key,
        mode_slug=CourseMode.AUDIT,
        defaults={'mode_display_name': 'Audit', 'min_price': 0, 'currency': 'usd', 'suggested_prices': ''},
    )
    enrollment = CourseEnrollment.objects.filter(user=learner, course_id=course_key).first()
    if enrollment is None:
        enrollment = CourseEnrollment.enroll(
            learner, course_key, mode=CourseMode.AUDIT, origin=EnrollmentOrigin.SELF,
        )
    else:
        enrollment.is_active = True
        enrollment.mode = CourseMode.AUDIT
        enrollment.origin = EnrollmentOrigin.SELF
        enrollment.completion_date = None
        enrollment.save()
    return enrollment


def read_branches(fixture_data):
    store = modulestore()
    keys = fixture_data['usage_keys']
    with store.branch_setting(ModuleStoreEnum.Branch.draft_preferred, fixture_data['course_key_object']):
        draft = [store.get_item(keys[block_type]) for block_type, _, _ in BLOCKS]
    with store.branch_setting(ModuleStoreEnum.Branch.published_only, fixture_data['course_key_object']):
        published = [store.get_item(keys[block_type]) for block_type, _, _ in BLOCKS]
    return draft, published


def assert_hierarchy(fixture_data, blocks):
    expected = [
        fixture_data['course_key_object'],
        fixture_data['usage_keys']['chapter'],
        fixture_data['usage_keys']['sequential'],
        fixture_data['usage_keys']['vertical'],
    ]
    for index, block in enumerate(blocks):
        if text_type(block.location) != text_type(fixture_data['usage_keys'][BLOCKS[index][0]]):
            raise RuntimeError('unexpected {} usage key: {}'.format(BLOCKS[index][0], block.location))
        if index < len(blocks) - 1:
            children = list(block.children)
            if len(children) != 1 or text_type(children[0]) != text_type(fixture_data['usage_keys'][BLOCKS[index + 1][0]]):
                raise RuntimeError('unexpected child list for {}'.format(block.location))
    if text_type(blocks[0].location.course_key) != text_type(expected[0]):
        raise RuntimeError('unexpected course key')


def identity_state(fixture_data, author, learner, enrollment):
    course_key = fixture_data['course_key_object']
    author_roles = list(CourseAccessRole.objects.filter(user=author).values_list('role', 'org', 'course_id'))
    learner_roles = list(CourseAccessRole.objects.filter(user=learner).values_list('role', 'org', 'course_id'))
    author_groups = list(author.groups.values_list('name', flat=True))
    learner_groups = list(learner.groups.values_list('name', flat=True))
    if author.is_staff or author.is_superuser or not author.is_active:
        raise RuntimeError('author must be active and non-staff/non-superuser')
    if learner.is_staff or learner.is_superuser or not learner.is_active:
        raise RuntimeError('learner must be active and non-staff/non-superuser')
    if author_groups != [STUDIO_ADMIN_ACCESS_GROUP]:
        raise RuntimeError('author groups are not exact: {!r}'.format(author_groups))
    if learner_groups:
        raise RuntimeError('learner has unexpected groups: {!r}'.format(learner_groups))
    expected_role = ('staff', course_key.org, course_key)
    if author_roles != [expected_role]:
        raise RuntimeError('author roles are not exact: {!r}'.format(author_roles))
    if learner_roles:
        raise RuntimeError('learner roles are not empty: {!r}'.format(learner_roles))
    if not enrollment.is_active or enrollment.mode != CourseMode.AUDIT:
        raise RuntimeError('learner enrollment is not active audit')
    return {
        'author': {'id': author.id, 'username': author.username, 'is_staff': author.is_staff,
                   'is_superuser': author.is_superuser, 'groups': author_groups, 'roles': author_roles},
        'learner': {'id': learner.id, 'username': learner.username, 'is_staff': learner.is_staff,
                    'is_superuser': learner.is_superuser, 'groups': learner_groups, 'roles': learner_roles},
        'enrollment': {'active': enrollment.is_active, 'mode': enrollment.mode,
                       'origin': enrollment.origin, 'completion_date': enrollment.completion_date},
    }


def branch_state(fixture_data):
    draft, published = read_branches(fixture_data)
    assert_hierarchy(fixture_data, draft)
    assert_hierarchy(fixture_data, published)
    store = modulestore()
    return {
        'draft': {'body': text_type(draft[-1].data), 'usage_key': text_type(draft[-1].location)},
        'published': {'body': text_type(published[-1].data), 'usage_key': text_type(published[-1].location)},
        'has_changes': bool(store.has_changes(draft[-1])),
        'published_by': published[-1].published_by,
        'published_on': published[-1].published_on,
        'draft_usage_keys': [text_type(block.location) for block in draft],
        'published_usage_keys': [text_type(block.location) for block in published],
    }


def assert_baseline(fixture_data, state):
    baseline = fixture_data['baseline']
    if state['draft']['body'].count(baseline) != 1 or state['published']['body'].count(baseline) != 1:
        raise RuntimeError('baseline body is not exact: {!r}'.format(state))
    if state['has_changes']:
        raise RuntimeError('baseline has unexpected draft changes')
    if fixture_data['after'] in state['draft']['body'] or fixture_data['after'] in state['published']['body']:
        raise RuntimeError('attempt marker remains during reset/preflight')


def assert_after(fixture_data, state, require_changes):
    marker = fixture_data['after']
    baseline = fixture_data['baseline']
    for branch_name in ('draft', 'published'):
        body = state[branch_name]['body']
        if body.count(marker) != 1 or baseline in body:
            raise RuntimeError('{} branch marker is not exact: {!r}'.format(branch_name, body))
    if state['has_changes'] != require_changes:
        raise RuntimeError('has_changes={} expected {}'.format(state['has_changes'], require_changes))


def provision(fixture_data):
    author, learner = configure_identities(fixture_data)
    ensure_sites(fixture_data)
    ensure_course(fixture_data, author)
    MockSearchEngine.create_test_file()
    course_store = modulestore()
    CourseAboutSearchIndexer.index_about_information(
        course_store,
        course_store.get_course(fixture_data['course_key_object']),
    )
    enrollment = ensure_enrollment(fixture_data, learner)
    state = branch_state(fixture_data)
    assert_baseline(fixture_data, state)
    identities = identity_state(fixture_data, author, learner, enrollment)
    payload = {
        'status': 'PROVISION_OK', 'runtime': RUNTIME, 'namespace': fixture_data['namespace'],
        'course_key': fixture_data['course_key'], 'state': state, 'identities': identities,
        'site_cms': fixture_data['site_cms'], 'site_lms': fixture_data['site_lms'],
    }
    write_evidence(fixture_data, 'provision.json', payload)
    emit('PROVISION_OK', payload)


def preflight(fixture_data):
    author = User.objects.get(username=fixture_data['author'], email=fixture_data['author_email'])
    learner = User.objects.get(username=fixture_data['learner'], email=fixture_data['learner_email'])
    enrollment = CourseEnrollment.objects.get(user=learner, course_id=fixture_data['course_key_object'])
    state = branch_state(fixture_data)
    assert_baseline(fixture_data, state)
    identities = identity_state(fixture_data, author, learner, enrollment)
    payload = {
        'status': 'STUDIO_PREFLIGHT_OK', 'runtime': RUNTIME, 'namespace': fixture_data['namespace'],
        'course_key': fixture_data['course_key'], 'state': state, 'identities': identities,
    }
    write_evidence(fixture_data, 'preflight.json', payload)
    emit('STUDIO_PREFLIGHT_OK', payload)


def reset(fixture_data):
    author = User.objects.get(username=fixture_data['author'], email=fixture_data['author_email'])
    learner = User.objects.get(username=fixture_data['learner'], email=fixture_data['learner_email'])
    enrollment = CourseEnrollment.objects.get(user=learner, course_id=fixture_data['course_key_object'])
    if not enrollment.is_active or enrollment.mode != CourseMode.AUDIT:
        raise RuntimeError('refusing reset without active audit enrollment')
    store = modulestore()
    with store.branch_setting(ModuleStoreEnum.Branch.draft_preferred, fixture_data['course_key_object']):
        with store.bulk_operations(fixture_data['course_key_object']):
            html = store.get_item(fixture_data['usage_keys']['html'])
            html.data = '<p>{}</p>'.format(fixture_data['baseline'])
            store.update_item(html, author.id)
    store.publish(fixture_data['usage_keys']['html'], author.id)
    clear_course_from_cache(fixture_data['course_key_object'])
    state = branch_state(fixture_data)
    assert_baseline(fixture_data, state)
    identities = identity_state(fixture_data, author, learner, enrollment)
    payload = {
        'status': 'STUDIO_RESET_OK', 'runtime': RUNTIME, 'namespace': fixture_data['namespace'],
        'course_key': fixture_data['course_key'], 'state': state, 'identities': identities,
    }
    write_evidence(fixture_data, 'reset-{}.json'.format(fixture_data['attempt']), payload)
    emit('STUDIO_RESET_OK', payload)


def midcondition(fixture_data):
    author = User.objects.get(username=fixture_data['author'], email=fixture_data['author_email'])
    learner = User.objects.get(username=fixture_data['learner'], email=fixture_data['learner_email'])
    enrollment = CourseEnrollment.objects.get(user=learner, course_id=fixture_data['course_key_object'])
    draft, published = read_branches(fixture_data)
    state = branch_state(fixture_data)
    marker = fixture_data['after']
    if marker not in state['draft']['body'] or fixture_data['baseline'] not in state['published']['body']:
        raise RuntimeError('save midcondition markers are wrong: {!r}'.format(state))
    if state['draft']['body'].count(marker) != 1 or state['published']['body'].count(fixture_data['baseline']) != 1:
        raise RuntimeError('save midcondition marker cardinality is wrong')
    if fixture_data['baseline'] in state['draft']['body'] or marker in state['published']['body']:
        raise RuntimeError('save changed the wrong branch')
    if not state['has_changes']:
        raise RuntimeError('save did not leave a draft change')
    identities = identity_state(fixture_data, author, learner, enrollment)
    payload = {
        'status': 'MIDCONDITION_OK', 'runtime': RUNTIME, 'attempt': fixture_data['attempt'],
        'namespace': fixture_data['namespace'], 'course_key': fixture_data['course_key'],
        'state': state, 'identities': identities,
        'draft_usage_key': text_type(draft[-1].location),
        'published_usage_key': text_type(published[-1].location),
    }
    write_evidence(fixture_data, 'midcondition-{}.json'.format(fixture_data['attempt']), payload)
    emit('MIDCONDITION_OK', payload)


def postflight(fixture_data):
    author = User.objects.get(username=fixture_data['author'], email=fixture_data['author_email'])
    learner = User.objects.get(username=fixture_data['learner'], email=fixture_data['learner_email'])
    enrollment = CourseEnrollment.objects.get(user=learner, course_id=fixture_data['course_key_object'])
    state = branch_state(fixture_data)
    assert_after(fixture_data, state, False)
    if state['published_by'] != author.id or state['published_on'] is None:
        raise RuntimeError('published editor metadata is wrong: {!r}'.format(state))
    identities = identity_state(fixture_data, author, learner, enrollment)
    payload = {
        'status': 'STUDIO_POSTFLIGHT_OK', 'runtime': RUNTIME, 'attempt': fixture_data['attempt'],
        'namespace': fixture_data['namespace'], 'course_key': fixture_data['course_key'],
        'state': state, 'identities': identities,
        'published_by_username': author.username,
        'published_at': text_type(state['published_on']),
        'checked_at': timezone.now(),
    }
    write_evidence(fixture_data, 'postflight-{}.json'.format(fixture_data['attempt']), payload)
    emit('STUDIO_POSTFLIGHT_OK', payload)


def main():
    if len(os.sys.argv) != 2 or os.sys.argv[1] not in ('provision', 'preflight', 'reset', 'midcondition', 'postflight'):
        raise SystemExit('usage: {} {{provision|preflight|reset|midcondition|postflight}}'.format(os.sys.argv[0]))
    fixture_data = fixture()
    globals()[os.sys.argv[1]](fixture_data)


if __name__ == '__main__':
    main()
