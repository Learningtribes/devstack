# -*- coding: utf-8 -*-
"""Provision, reset, preflight, and verify the isolated discussion gate."""
from __future__ import absolute_import, division, print_function, unicode_literals

import hashlib
import json
import os
import re
import sys
from datetime import datetime

import django
import pytz
import requests
from six import text_type
from six.moves.urllib.parse import urlparse

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.contrib.sites.models import Site  # noqa: E402
from course_modes.models import CourseMode  # noqa: E402
from courseware.courses import get_course_with_access  # noqa: E402
from django_comment_common.models import (  # noqa: E402
    DiscussionsIdMapping,
    FORUM_ROLE_STUDENT,
    ForumsConfig,
    Role,
)
from django_comment_common.utils import (  # noqa: E402
    CourseDiscussionSettings,
    seed_permissions_roles,
    set_course_discussion_settings,
)
from lms.lib import comment_client as cc  # noqa: E402
from lms.lib.comment_client.utils import check_forum_heartbeat  # noqa: E402
from opaque_keys.edx.keys import CourseKey  # noqa: E402
from openedx.core.djangoapps.content.block_structure.api import clear_course_from_cache  # noqa: E402
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview  # noqa: E402
from openedx.core.djangoapps.content.course_structures.tasks import update_course_structure  # noqa: E402
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration  # noqa: E402
from student.models import (  # noqa: E402
    CourseAccessRole,
    CourseEnrollment,
    EnrollmentOrigin,
    Registration,
    UserProfile,
)
from xmodule.contentstore.content import StaticContent  # noqa: E402
from xmodule.contentstore.django import contentstore  # noqa: E402
from xmodule.course_module import COURSE_RELEASED_STATUS  # noqa: E402
from xmodule.modulestore import ModuleStoreEnum  # noqa: E402
from xmodule.modulestore.django import modulestore  # noqa: E402
from xmodule.modulestore.exceptions import DuplicateCourseError, ItemNotFoundError  # noqa: E402
from xmodule.tabs import CourseTab, CourseTabList  # noqa: E402


DISPLAY_NAME = 'P1-B Discussion Read Write'
DISCUSSION_SECTION = 'Discussion Section'
DISCUSSION_SUBSECTION = 'Discussion Subsection'
DISCUSSION_UNIT = 'Discussion Unit'
DISCUSSION_DISPLAY_NAME = 'Discussion Topic'
DISCUSSION_CATEGORY = 'P1-B Discussion'
DISCUSSION_TARGET = 'Read Write Topic'
THREAD_TITLE = 'P1B_DISCUSSION_THREAD_OK'
THREAD_BODY = 'P1B_DISCUSSION_BODY_OK'
REPLY_BODY = 'P1B_DISCUSSION_REPLY_OK'
COURSE_START = datetime(2026, 8, 1, tzinfo=pytz.UTC)
COURSE_END = datetime(2027, 8, 1, tzinfo=pytz.UTC)
IMAGE_NAME = 'p1b_discussion_read_write.jpg'

RUNTIME_FIXTURES = {
    'py36': {
        'username': 'qadiscuss_py36',
        'email': 'qadiscuss_py36@example.com',
        'author': 'qadiscuss_author_py36',
        'author_email': 'qadiscuss_author_py36@example.com',
        'course_key': 'course-v1:QA+DiscussionRW+Py36',
        'discussion_id': 'p1b_discussion_rw_py36',
        'namespace': 'py36_r1_p1b_discussion_rw_py36_r1',
        'site_domain': 'localhost:18137',
    },
    'py27': {
        'username': 'qadiscuss_py27',
        'email': 'qadiscuss_py27@example.com',
        'author': 'qadiscuss_author_py27',
        'author_email': 'qadiscuss_author_py27@example.com',
        'course_key': 'course-v1:QA+DiscussionRW+Py27',
        'discussion_id': 'p1b_discussion_rw_py27',
        'namespace': 'py36_r1_p1b_discussion_rw_py27_r1',
        'site_domain': 'localhost:18138',
    },
}


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError('{} is required'.format(name))
    return value


def _fixture():
    runtime = _required('PY36_R1_DISCUSSION_RUNTIME')
    if runtime not in RUNTIME_FIXTURES:
        raise RuntimeError('PY36_R1_DISCUSSION_RUNTIME must be py36 or py27')
    fixture = dict(RUNTIME_FIXTURES[runtime])
    expected_env = {
        'username': 'PY36_R1_DISCUSSION_USERNAME',
        'email': 'PY36_R1_DISCUSSION_EMAIL',
        'course_key': 'PY36_R1_DISCUSSION_COURSE_KEY',
        'discussion_id': 'PY36_R1_DISCUSSION_ID',
        'namespace': 'PY36_R1_DISCUSSION_NAMESPACE',
        'site_domain': 'PY36_R1_DISCUSSION_SITE_DOMAIN',
    }
    for key, env_name in expected_env.items():
        value = os.environ.get(env_name, fixture[key])
        if value != fixture[key]:
            raise RuntimeError('{} must equal the gate-owned value {!r}'.format(env_name, fixture[key]))
        fixture[key] = value
    fixture.update({
        'runtime': runtime,
        'course_key_object': CourseKey.from_string(fixture['course_key']),
        'forum_url': _required('COMMENTS_SERVICE_URL').rstrip('/'),
        'comments_service_key': _required('COMMENTS_SERVICE_KEY'),
        'mongo_uri': _required('PY36_R1_DISCUSSION_MONGO_URI'),
        'search_server': _required('PY36_R1_DISCUSSION_SEARCH_SERVER').rstrip('/'),
        'evidence_dir': _required('PY36_R1_DISCUSSION_EVIDENCE_DIR'),
    })
    return fixture


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return text_type(value)


def _write_evidence(fixture, name, payload):
    if not os.path.isdir(fixture['evidence_dir']):
        os.makedirs(fixture['evidence_dir'])
    path = os.path.join(fixture['evidence_dir'], name)
    with open(path, 'w') as evidence_file:
        evidence_file.write(json.dumps(payload, default=_json_default, sort_keys=True, indent=2))
        evidence_file.write('\n')
    return path


def _get_or_create_user(username, email, is_staff):
    user, _ = User.objects.get_or_create(username=username, defaults={'email': email})
    user.email = email
    user.is_active = True
    user.is_staff = is_staff
    user.is_superuser = is_staff
    user.save()
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'name': username})
    profile.name = username
    if hasattr(profile, 'lt_learning_group'):
        profile.lt_learning_group = None
    profile.save()
    Registration.objects.get_or_create(
        user=user,
        defaults={
            'activation_key': hashlib.md5(
                'p1b-discussion-{}'.format(username).encode('utf8')
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


def _save_course_image(fixture):
    image_key = StaticContent.compute_location(fixture['course_key_object'], IMAGE_NAME)
    stored_image = contentstore().find(image_key, throw_on_not_found=False)
    if stored_image is None or stored_image.length < 1024:
        image_path = os.path.join(
            settings.REPO_ROOT,
            'common/test/data/conditional_and_poll/static/images/course_image.jpg',
        )
        with open(image_path, 'rb') as image_file:
            contentstore().save(StaticContent(image_key, IMAGE_NAME, 'image/jpeg', image_file))
    stored_image = contentstore().find(image_key, throw_on_not_found=False)
    if stored_image is None or stored_image.length < 1024:
        raise RuntimeError('course image is missing or too small')
    return image_key, stored_image.length


def _published_fixture(fixture):
    course_key = fixture['course_key_object']
    store = modulestore()
    usage_keys = [
        course_key.make_usage_key('chapter', 'discussion_section'),
        course_key.make_usage_key('sequential', 'discussion_subsection'),
        course_key.make_usage_key('vertical', 'discussion_unit'),
        course_key.make_usage_key('discussion', 'discussion_topic'),
    ]
    with store.branch_setting(ModuleStoreEnum.Branch.published_only, course_key):
        course = store.get_course(course_key)
        blocks = [store.get_item(usage_key) for usage_key in usage_keys]
    if course is None or course.course_status != COURSE_RELEASED_STATUS:
        raise RuntimeError('published released course is missing: {}'.format(course_key))
    if blocks[-1].display_name != DISCUSSION_DISPLAY_NAME:
        raise RuntimeError('published Discussion XBlock display name is incorrect')
    if blocks[-1].discussion_id != fixture['discussion_id']:
        raise RuntimeError('published Discussion XBlock ID is not gate-owned')
    if blocks[-1].discussion_category != DISCUSSION_CATEGORY:
        raise RuntimeError('published Discussion XBlock category is incorrect')
    if blocks[-1].discussion_target != DISCUSSION_TARGET:
        raise RuntimeError('published Discussion XBlock target is incorrect')
    discussion_tab = CourseTabList.get_discussion(course)
    if discussion_tab is None or discussion_tab.type != 'discussion':
        raise RuntimeError('published course has no internal Discussion tab')
    if fixture['discussion_id'] in course.top_level_discussion_topic_ids:
        raise RuntimeError('gate-owned Discussion XBlock ID is duplicated as a top-level topic')
    return course, blocks


def _configure_course(fixture, author):
    course_key = fixture['course_key_object']
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
            course.course_image = IMAGE_NAME
            course.discussion_link = None
            course.discussion_topics = {}
            tabs = list(course.tabs or [])
            tabs = [tab for tab in tabs if tab is not None and tab.type != 'external_discussion']
            if not any(tab.type == 'discussion' for tab in tabs):
                tabs.append(CourseTab.load('discussion'))
            course.tabs = tabs
            course = store.update_item(course, author.id)

            parent_location = course.location
            blocks = (
                ('chapter', 'discussion_section', DISCUSSION_SECTION, {}),
                ('sequential', 'discussion_subsection', DISCUSSION_SUBSECTION, {}),
                ('vertical', 'discussion_unit', DISCUSSION_UNIT, {}),
                ('discussion', 'discussion_topic', DISCUSSION_DISPLAY_NAME, {
                    'discussion_id': fixture['discussion_id'],
                    'discussion_category': DISCUSSION_CATEGORY,
                    'discussion_target': DISCUSSION_TARGET,
                    'sort_key': DISCUSSION_TARGET,
                }),
            )
            for block_type, block_id, display_name, extra_fields in blocks:
                fields = {'display_name': display_name}
                fields.update(extra_fields)
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

    _published_fixture(fixture)
    image_key, image_length = _save_course_image(fixture)
    CourseOverview.load_from_module_store(course_key)
    set_course_discussion_settings(
        course_key,
        division_scheme=CourseDiscussionSettings.NONE,
        divided_discussions=[],
        always_divide_inline_discussions=False,
    )
    discussion_blocks = [
        block for block in store.get_items(course_key, qualifiers={'category': 'discussion'}, include_orphans=False)
        if block.discussion_id == fixture['discussion_id']
    ]
    if len(discussion_blocks) != 1:
        raise RuntimeError('expected exactly one gate-owned Discussion XBlock')
    DiscussionsIdMapping.update_mapping(
        course_key,
        {fixture['discussion_id']: text_type(discussion_blocks[0].location)},
    )
    update_course_structure(text_type(course_key))
    clear_course_from_cache(course_key)
    return image_key, image_length


def _configure_site_and_enrollment(fixture, learner):
    course_key = fixture['course_key_object']
    site, _ = Site.objects.get_or_create(
        domain=fixture['site_domain'],
        defaults={'name': 'P1-B discussion {}'.format(fixture['runtime'])},
    )
    site.name = 'P1-B discussion {}'.format(fixture['runtime'])
    site.save()
    site_configuration, _ = SiteConfiguration.objects.get_or_create(
        site=site,
        defaults={'enabled': True, 'values': {}},
    )
    values = dict(site_configuration.values or {})
    values.update({
        'course_org_filter': course_key.org,
        'DISCUSSION_EXCLUDE': [],
        'ENABLE_DISCUSSION_SERVICE': True,
    })
    site_configuration.enabled = True
    site_configuration.values = values
    site_configuration.save()

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

    enrollment = CourseEnrollment.objects.filter(user=learner, course_id=course_key).first()
    if enrollment is None or not enrollment.is_active:
        enrollment = CourseEnrollment.enroll(
            learner,
            course_key,
            mode=CourseMode.AUDIT,
            origin=EnrollmentOrigin.SELF,
        )
    else:
        enrollment.mode = CourseMode.AUDIT
        enrollment.origin = EnrollmentOrigin.SELF
        enrollment.completion_date = None
        enrollment.save()
    seed_permissions_roles(course_key)
    for role in Role.objects.filter(users=learner, course_id=course_key).exclude(name=FORUM_ROLE_STUDENT):
        role.users.remove(learner)
    Role.objects.get(name=FORUM_ROLE_STUDENT, course_id=course_key).users.add(learner)
    if not CourseEnrollment.is_enrolled(learner, course_key):
        raise RuntimeError('learner is not actively enrolled')
    return enrollment


def _configure_forums():
    config = ForumsConfig.current()
    config.enabled = True
    config.connection_timeout = 5.0
    config.save()
    if not config.enabled or config.connection_timeout > 5.0:
        raise RuntimeError('ForumsConfig is not enabled with a bounded timeout')


def _sync_forum_user(learner):
    forum_user = cc.User.from_django_user(learner)
    forum_user.save()
    forum_user.retrieve()
    if forum_user.external_id != text_type(learner.id) or forum_user.username != learner.username:
        raise RuntimeError('comments-service user did not synchronize correctly')
    return forum_user


def _forum_request(fixture, method, path, data=None, params=None):
    headers = {'X-Edx-Api-Key': fixture['comments_service_key']}
    response = requests.request(
        method,
        fixture['forum_url'] + path,
        headers=headers,
        data=data,
        params=params,
        timeout=5,
    )
    return response


def _forum_heartbeat(fixture):
    response = requests.get(fixture['forum_url'] + '/heartbeat', timeout=5)
    if response.status_code != 200:
        raise RuntimeError('forum heartbeat status is {}'.format(response.status_code))
    try:
        body = response.json()
    except ValueError:
        raise RuntimeError('forum heartbeat is not JSON')
    if body.get('OK') is not True:
        raise RuntimeError('forum heartbeat did not report OK=true')
    return {'status': response.status_code, 'body': body}


def _comments_heartbeat():
    result = check_forum_heartbeat()
    if result[1] is not True:
        raise RuntimeError('LMS comments-service heartbeat failed: {}'.format(result[2]))
    return {'name': result[0], 'ok': result[1], 'message': result[2]}


def _mongo_database(fixture):
    try:
        from pymongo import MongoClient
    except ImportError:
        raise RuntimeError('pymongo is required for bounded comments-state verification')
    parsed = urlparse(fixture['mongo_uri'])
    database_name = parsed.path.lstrip('/')
    if not database_name:
        raise RuntimeError('Mongo URI has no database')
    # PyMongo 2.9 (the Py2 control) predates serverSelectionTimeoutMS. These
    # timeouts bound both connection establishment and verifier operations on
    # the old and new runtimes.
    client = MongoClient(fixture['mongo_uri'], connectTimeoutMS=5000, socketTimeoutMS=5000)
    client.admin.command('ping')
    return client, client[database_name]


def _cursor_count(collection, query):
    return collection.find(query).count()


def _object_id(value, label):
    try:
        from bson.objectid import ObjectId
    except ImportError:
        raise RuntimeError('bson is required for bounded comments-state verification')
    value = text_type(value)
    if not ObjectId.is_valid(value):
        raise RuntimeError('{} is not a valid Mongo ObjectId: {!r}'.format(label, value))
    return ObjectId(value)


def _mongo_state(fixture, learner, thread_ids=None, comment_ids=None):
    client, database = _mongo_database(fixture)
    try:
        course_key = fixture['course_key']
        discussion_id = fixture['discussion_id']
        thread_query = {
            '_type': 'CommentThread',
            'course_id': course_key,
            'commentable_id': discussion_id,
        }
        thread_documents = list(database.contents.find(thread_query))
        all_thread_ids = [text_type(document.get('_id')) for document in thread_documents]
        requested_thread_ids = [text_type(value) for value in (thread_ids or [])]
        requested_comment_ids = [text_type(value) for value in (comment_ids or [])]
        comment_query = {'_type': 'Comment', 'course_id': course_key}
        comment_documents = list(database.contents.find(comment_query))
        user_documents = list(database.users.find({'external_id': text_type(learner.id)}))
        es_documents = _elasticsearch_documents(fixture)
        return {
            'mongo_database': database.name,
            'threads': {
                'count': len(thread_documents),
                'ids': all_thread_ids,
                'documents': thread_documents,
            },
            'comments': {
                'count': len(comment_documents),
                'ids': [text_type(document.get('_id')) for document in comment_documents],
                'documents': comment_documents,
            },
            'comments_service_user': {
                'count_by_external_id': len(user_documents),
                'count_by_username': _cursor_count(database.users, {'username': learner.username}),
                'ids': [text_type(document.get('_id')) for document in user_documents],
                'documents': user_documents,
            },
            'elasticsearch': es_documents,
            'requested_thread_ids': requested_thread_ids,
            'requested_comment_ids': requested_comment_ids,
        }
    finally:
        client.close()


def _elasticsearch_documents(fixture):
    refresh = requests.post(fixture['search_server'] + '/content/_refresh', timeout=5)
    if refresh.status_code >= 300:
        raise RuntimeError('Elasticsearch refresh failed: {}'.format(refresh.status_code))
    query = {
        'query': {'match_phrase': {'course_id': fixture['course_key']}},
        'size': 100,
    }
    response = requests.post(
        fixture['search_server'] + '/content/_search',
        headers={'Content-Type': 'application/json'},
        data=json.dumps(query),
        timeout=5,
    )
    if response.status_code != 200:
        raise RuntimeError('Elasticsearch search failed: {}'.format(response.status_code))
    payload = response.json()
    hits = [
        hit for hit in payload.get('hits', {}).get('hits', [])
        if hit.get('_source', {}).get('course_id') == fixture['course_key']
    ]
    return {
        'index': 'content',
        'total': len(hits),
        'ids': [text_type(hit.get('_id')) for hit in hits],
        'documents': hits,
    }


def _state_file(fixture):
    path = os.environ.get('PY36_R1_DISCUSSION_STATE_FILE')
    if not path:
        return None
    if not os.path.isfile(path):
        raise RuntimeError('browser state file does not exist: {}'.format(path))
    with open(path) as state_file:
        state = json.load(state_file)
    expected = {
        'runtime': fixture['runtime'],
        'course_key': fixture['course_key'],
        'discussion_id': fixture['discussion_id'],
    }
    actual = {
        'runtime': state.get('runtime'),
        'course_key': state.get('course_key'),
        'discussion_id': state.get('discussion_id'),
    }
    if actual != expected:
        raise RuntimeError('state file is outside the reset allowlist: {!r}'.format(actual))
    for key in ('thread_id', 'comment_id'):
        value = state.get(key)
        if not value or not re.match(r'^[A-Za-z0-9_-]+$', text_type(value)):
            raise RuntimeError('state file has an invalid {}'.format(key))
    return state


def _delete_dependent_state(fixture, state):
    thread_id = text_type(state['thread_id'])
    comment_id = text_type(state['comment_id'])
    response = _forum_request(fixture, 'delete', '/api/v1/threads/{}'.format(thread_id))
    if response.status_code != 200:
        raise RuntimeError('comments-service thread delete failed: {}'.format(response.status_code))

    client, database = _mongo_database(fixture)
    try:
        content_ids = [
            _object_id(thread_id, 'thread_id'),
            _object_id(comment_id, 'comment_id'),
        ]
        for collection_name in ('activities', 'notifications', 'subscriptions'):
            collection = database[collection_name]
            collection.delete_many({
                '$or': [
                    {'source_id': {'$in': content_ids}},
                    {'target_id': {'$in': content_ids}},
                    {'activity_id': {'$in': content_ids}},
                    {'object_id': {'$in': content_ids}},
                ],
            })
        database.users.update_many(
            {'external_id': text_type(state.get('user_id'))},
            {'$pull': {'read_states': {'course_id': fixture['course_key']}}},
        )
    finally:
        client.close()


def _assert_empty(fixture, learner, state=None):
    thread_ids = [state['thread_id']] if state else []
    comment_ids = [state['comment_id']] if state else []
    current = _mongo_state(fixture, learner, thread_ids=thread_ids, comment_ids=comment_ids)
    if current['threads']['count'] != 0 or current['comments']['count'] != 0:
        raise RuntimeError('gate-owned Mongo discussion content remains: {}'.format(current))
    if state:
        stale_threads = set(thread_ids).intersection(current['threads']['ids'])
        stale_comments = set(comment_ids).intersection(current['comments']['ids'])
        if stale_threads or stale_comments:
            raise RuntimeError('captured content remains after reset')
        stale_es = set(thread_ids + comment_ids).intersection(current['elasticsearch']['ids'])
        if stale_es:
            raise RuntimeError('captured Elasticsearch documents remain after reset')
    if current['elasticsearch']['total'] not in (0, '0'):
        raise RuntimeError('gate-owned Elasticsearch course documents remain: {}'.format(current['elasticsearch']))
    return current


def provision(fixture):
    author = _get_or_create_user(fixture['author'], fixture['author_email'], True)
    learner = _get_or_create_user(fixture['username'], fixture['email'], False)
    image_key, image_length = _configure_course(fixture, author)
    enrollment = _configure_site_and_enrollment(fixture, learner)
    _configure_forums()
    forum_user = _sync_forum_user(learner)
    print('PROVISION_OK {}'.format(json.dumps({
        'runtime': fixture['runtime'],
        'namespace': fixture['namespace'],
        'user_id': learner.id,
        'forum_user_id': forum_user.id,
        'course_key': fixture['course_key'],
        'discussion_id': fixture['discussion_id'],
        'image_key': text_type(image_key),
        'image_length': image_length,
        'enrollment_id': enrollment.id,
    }, sort_keys=True)))


def reset_and_preflight(fixture):
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    learner.is_staff = False
    learner.is_superuser = False
    learner.is_active = True
    learner.save()
    course_key = fixture['course_key_object']
    CourseAccessRole.objects.filter(user=learner, org=course_key.org).delete()
    if not CourseEnrollment.is_enrolled(learner, course_key):
        raise RuntimeError('active audit enrollment was not preserved')
    enrollment = CourseEnrollment.objects.get(user=learner, course_id=course_key)
    if enrollment.mode != CourseMode.AUDIT:
        raise RuntimeError('learner enrollment mode is not audit')
    non_student_roles = list(
        Role.objects.filter(users=learner, course_id=course_key).exclude(name=FORUM_ROLE_STUDENT)
    )
    if non_student_roles:
        raise RuntimeError('learner has privileged forum roles: {!r}'.format(non_student_roles))
    if getattr(learner.profile, 'lt_learning_group', None):
        raise RuntimeError('learner is in an excluded learning group')

    state = _state_file(fixture)
    if state:
        _delete_dependent_state(fixture, state)
    _configure_forums()
    forum_heartbeat = _forum_heartbeat(fixture)
    comments_heartbeat = _comments_heartbeat()
    forum_user = _sync_forum_user(learner)
    course, blocks = _published_fixture(fixture)
    accessible_course = get_course_with_access(learner, 'load', course_key)
    if accessible_course.id != course.id:
        raise RuntimeError('learner cannot read the published course')
    current = _assert_empty(fixture, learner, state=state)
    result = {
        'runtime': fixture['runtime'],
        'namespace': fixture['namespace'],
        'service': {
            'lms_site': fixture['site_domain'],
            'forum_url': fixture['forum_url'],
            'mongo_database': current['mongo_database'],
            'elasticsearch_server': fixture['search_server'],
            'elasticsearch_index': 'content',
        },
        'user': {
            'id': learner.id,
            'username': learner.username,
            'email': learner.email,
            'comments_service_id': forum_user.id,
            'comments_service_external_id': forum_user.external_id,
        },
        'course_key': fixture['course_key'],
        'usage_key': text_type(blocks[-1].location),
        'discussion_id': fixture['discussion_id'],
        'topic': {
            'display_name': DISCUSSION_DISPLAY_NAME,
            'category': DISCUSSION_CATEGORY,
            'target': DISCUSSION_TARGET,
        },
        'enrollment': {
            'id': enrollment.id,
            'active': enrollment.is_active,
            'mode': enrollment.mode,
            'origin': enrollment.origin,
        },
        'privilege': {
            'is_staff': learner.is_staff,
            'is_superuser': learner.is_superuser,
            'course_access_roles': [],
            'non_student_forum_roles': [],
            'learning_group': getattr(learner.profile, 'lt_learning_group', None),
        },
        'mongo': {
            'threads': current['threads']['count'],
            'comments': current['comments']['count'],
            'comments_service_user_by_external_id': current['comments_service_user']['count_by_external_id'],
        },
        'elasticsearch': {
            'index': 'content',
            'course_document_count': current['elasticsearch']['total'],
            'document_ids': current['elasticsearch']['ids'],
        },
        'forum_heartbeat': forum_heartbeat,
        'lms_comments_heartbeat': comments_heartbeat,
        'published': {
            'course_status': course.course_status,
            'discussion_tab': True,
            'discussion_xblock': text_type(blocks[-1].location),
        },
    }
    attempt = os.environ.get('PY36_R1_DISCUSSION_ATTEMPT', 'preflight')
    _write_evidence(fixture, 'precondition-{}.json'.format(attempt), result)
    print('PRECONDITION_OK {}'.format(json.dumps(result, default=_json_default, sort_keys=True)))


def _document_id(document):
    return text_type(document.get('_id'))


def postflight(fixture):
    state = _state_file(fixture)
    if not state:
        raise RuntimeError('postflight requires a browser state file')
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    thread_id = text_type(state['thread_id'])
    comment_id = text_type(state['comment_id'])
    thread_object_id = _object_id(thread_id, 'thread_id')
    comment_object_id = _object_id(comment_id, 'comment_id')
    client, database = _mongo_database(fixture)
    try:
        thread_documents = list(database.contents.find({
            '_type': 'CommentThread',
            'course_id': fixture['course_key'],
            'commentable_id': fixture['discussion_id'],
            '_id': thread_object_id,
            'title': THREAD_TITLE,
            'body': THREAD_BODY,
            'author_id': text_type(learner.id),
            'visible': {'$ne': False},
        }))
        if len(thread_documents) != 1:
            raise RuntimeError('expected one exact persisted CommentThread, got {}'.format(len(thread_documents)))
        thread_document = thread_documents[0]
        comment_documents = list(database.contents.find({
            '_type': 'Comment',
            'course_id': fixture['course_key'],
            'comment_thread_id': thread_object_id,
            '_id': comment_object_id,
            'body': REPLY_BODY,
            'author_id': text_type(learner.id),
        }))
        top_level_comments = [
            document for document in comment_documents
            if not document.get('parent_ids') and not document.get('parent_id')
        ]
        if len(top_level_comments) != 1:
            raise RuntimeError('expected one exact top-level Comment, got {}'.format(len(top_level_comments)))
        comment_document = top_level_comments[0]
        if thread_document.get('comment_count') != 1:
            raise RuntimeError('thread comment_count is not one')
        if thread_document.get('last_activity_at') < comment_document.get('created_at'):
            raise RuntimeError('thread last_activity_at predates the reply')
        user_documents = list(database.users.find({'external_id': text_type(learner.id)}))
        if len(user_documents) != 1 or user_documents[0].get('username') != learner.username:
            raise RuntimeError('comments-service user is not unique and correct')
    finally:
        client.close()

    service_thread = _forum_request(
        fixture,
        'get',
        '/api/v1/threads/{}'.format(thread_id),
        params={
            'with_responses': 'true',
            'recursive': 'true',
            'user_id': text_type(learner.id),
        },
    )
    if service_thread.status_code != 200:
        raise RuntimeError('comments-service thread read failed: {}'.format(service_thread.status_code))
    service_payload = service_thread.json()
    if service_payload.get('title') != THREAD_TITLE or service_payload.get('body') != THREAD_BODY:
        raise RuntimeError('comments-service thread body does not match')
    service_json = json.dumps(service_payload)
    if REPLY_BODY not in service_json or comment_id not in service_json:
        raise RuntimeError('comments-service reply read does not match captured ID/body')

    current = _mongo_state(fixture, learner, thread_ids=[thread_id], comment_ids=[comment_id])
    es_ids = set(current['elasticsearch']['ids'])
    if thread_id not in es_ids or comment_id not in es_ids:
        raise RuntimeError('Mongo content is persisted but both Elasticsearch IDs are not queryable')
    course_threads = [
        document for document in current['threads']['documents']
        if _document_id(document) == thread_id and document.get('title') == THREAD_TITLE
    ]
    course_comments = [
        document for document in current['comments']['documents']
        if _document_id(document) == comment_id and document.get('body') == REPLY_BODY
    ]
    enrollment = CourseEnrollment.objects.get(user=learner, course_id=fixture['course_key_object'])
    course_access_roles = list(CourseAccessRole.objects.filter(user=learner, org=fixture['course_key_object'].org))
    if not enrollment.is_active or enrollment.mode != CourseMode.AUDIT:
        raise RuntimeError('learner is not actively enrolled in audit mode')
    if learner.is_staff or learner.is_superuser or course_access_roles:
        raise RuntimeError('learner gained privileged access')
    result = {
        'runtime': fixture['runtime'],
        'namespace': fixture['namespace'],
        'course_key': fixture['course_key'],
        'discussion_id': fixture['discussion_id'],
        'thread_id': thread_id,
        'comment_id': comment_id,
        'user_id': learner.id,
        'thread_count': len(course_threads),
        'comment_count': len(course_comments),
        'thread_comment_count': thread_documents[0].get('comment_count'),
        'thread_last_activity_at': thread_documents[0].get('last_activity_at'),
        'mongo': current,
        'elasticsearch': current['elasticsearch'],
        'comments_service_read': {
            'status': service_thread.status_code,
            'thread_id': service_payload.get('id'),
            'reply_marker_present': REPLY_BODY in service_json,
        },
        'enrollment': {
            'active': enrollment.is_active,
            'mode': enrollment.mode,
            'origin': enrollment.origin,
        },
        'privilege': {
            'is_staff': learner.is_staff,
            'is_superuser': learner.is_superuser,
            'course_access_roles': [],
        },
    }
    attempt = os.environ.get('PY36_R1_DISCUSSION_ATTEMPT', 'postflight')
    _write_evidence(fixture, 'postcondition-{}.json'.format(attempt), result)
    print('POSTCONDITION_OK {}'.format(json.dumps(result, default=_json_default, sort_keys=True)))


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('provision', 'reset', 'postflight'):
        raise SystemExit('usage: {} {{provision|reset|postflight}}'.format(sys.argv[0]))
    fixture = _fixture()
    if sys.argv[1] == 'provision':
        provision(fixture)
    elif sys.argv[1] == 'reset':
        reset_and_preflight(fixture)
    else:
        postflight(fixture)


if __name__ == '__main__':
    main()
