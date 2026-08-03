# -*- coding: utf-8 -*-
"""Provision, reset, and verify the disposable P1-B grading fixture."""
from __future__ import absolute_import, division, print_function, unicode_literals

import hashlib
import json
import os
import re
import sys
from datetime import datetime

import django
import pytz
from lxml import etree
from six import text_type

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.contrib.sites.models import Site  # noqa: E402
from waffle.models import Switch  # noqa: E402

from completion import waffle as completion_waffle  # noqa: E402
from completion.models import BlockCompletion  # noqa: E402
from course_modes.models import CourseMode  # noqa: E402
from courseware.courses import get_course_with_access  # noqa: E402
from courseware.models import StudentModule  # noqa: E402
from django_comment_common.models import ForumsConfig  # noqa: E402
from lms.djangoapps.certificates.models import GeneratedCertificate  # noqa: E402
from lms.djangoapps.grades.config.models import (  # noqa: E402
    CoursePersistentGradesFlag,
    PersistentGradesEnabledFlag,
)
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory  # noqa: E402
from lms.djangoapps.grades.models import (  # noqa: E402
    PersistentCourseGrade,
    PersistentCourseProgress,
    PersistentSubsectionGrade,
    PersistentSubsectionGradeOverride,
)
from lms.djangoapps.grades.transformer import GradesTransformer  # noqa: E402
from openedx.core.djangoapps.content.block_structure.api import (  # noqa: E402
    clear_course_from_cache,
    update_course_in_cache,
)
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview  # noqa: E402
from openedx.core.djangoapps.content.course_structures.tasks import update_course_structure  # noqa: E402
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration  # noqa: E402
from opaque_keys.edx.keys import CourseKey  # noqa: E402
from student.models import (  # noqa: E402
    CourseAccessRole,
    CourseEnrollment,
    EnrollmentOrigin,
    Registration,
    UserProfile,
    anonymous_id_for_user,
)
from xmodule.contentstore.content import StaticContent  # noqa: E402
from xmodule.contentstore.django import contentstore  # noqa: E402
from xmodule.course_module import COURSE_RELEASED_STATUS  # noqa: E402
from xmodule.modulestore import ModuleStoreEnum  # noqa: E402
from xmodule.modulestore.django import modulestore  # noqa: E402
from xmodule.modulestore.exceptions import DuplicateCourseError, ItemNotFoundError  # noqa: E402

try:
    from submissions.models import Score as SubmissionScore  # noqa: E402
    from submissions.models import Submission  # noqa: E402
except ImportError:  # pragma: no cover - the dependency is image-provided
    Submission = None
    SubmissionScore = None


COURSE_DISPLAY_NAME = 'P1-B Grading Mutation'
COURSE_START = datetime(2026, 8, 1, tzinfo=pytz.UTC)
COURSE_END = datetime(2027, 8, 1, tzinfo=pytz.UTC)
PROBLEM_XML = '''<problem>
  <p>Choose the correct grading checkpoint.</p>
  <multiplechoiceresponse>
    <choicegroup type="MultipleChoice" shuffle="false">
      <choice correct="false">GRADING_WRONG</choice>
      <choice correct="true">GRADING_CORRECT</choice>
    </choicegroup>
  </multiplechoiceresponse>
</problem>'''
GRADING_POLICY = {
    'GRADER': [{
        'type': 'Homework',
        'min_count': 1,
        'drop_count': 0,
        'short_label': 'HW',
        'weight': 1.0,
    }],
    'GRADE_CUTOFFS': {'Pass': 0.5},
}
BASE_BLOCKS = (
    ('chapter', 'grading_section', 'Grading Section'),
    ('sequential', 'grading_subsection', 'Grading Subsection'),
    ('vertical', 'grading_unit', 'Grading Unit'),
)
RUNTIME_FIXTURES = {
    'py36': {
        'username': 'qagrade_py36',
        'email': 'qagrade_py36@example.com',
        'author': 'qagrade_author_py36',
        'author_email': 'qagrade_author_py36@example.com',
        'course_key': 'course-v1:QA+GradingMutation+Py36',
        'problem_id': 'p1b_grading_problem_py36',
        'namespace': 'py36_r1_p1b_grading_mutation_py36_r1',
        'site_domain': 'localhost:18139',
        'image_name': 'p1b_grading_mutation_py36_r1.jpg',
    },
    'py27': {
        'username': 'qagrade_py27',
        'email': 'qagrade_py27@example.com',
        'author': 'qagrade_author_py27',
        'author_email': 'qagrade_author_py27@example.com',
        'course_key': 'course-v1:QA+GradingMutation+Py27',
        'problem_id': 'p1b_grading_problem_py27',
        'namespace': 'py36_r1_p1b_grading_mutation_py27_r1',
        'site_domain': 'localhost:18140',
        'image_name': 'p1b_grading_mutation_py27_r1.jpg',
    },
}


def _blocks(fixture):
    return BASE_BLOCKS + (
        ('problem', fixture['problem_id'], 'Grading Checkpoint'),
    )


def _fixture():
    runtime = os.environ.get('PY36_R1_GRADING_RUNTIME')
    if runtime not in RUNTIME_FIXTURES:
        raise RuntimeError('PY36_R1_GRADING_RUNTIME must be py36 or py27')
    fixture = dict(RUNTIME_FIXTURES[runtime])
    fixture['runtime'] = runtime
    expected = {
        'username': 'PY36_R1_GRADING_USERNAME',
        'email': 'PY36_R1_GRADING_EMAIL',
        'course_key': 'PY36_R1_GRADING_COURSE_KEY',
        'namespace': 'PY36_R1_GRADING_NAMESPACE',
        'site_domain': 'PY36_R1_GRADING_SITE_DOMAIN',
    }
    for key, env_name in expected.items():
        value = os.environ.get(env_name, fixture[key])
        if value != fixture[key]:
            raise RuntimeError('{} must equal the gate-owned value {!r}'.format(env_name, fixture[key]))
        fixture[key] = value
    fixture['course_key_object'] = CourseKey.from_string(fixture['course_key'])
    fixture['blocks'] = _blocks(fixture)
    fixture['usage_keys'] = {
        block_type: fixture['course_key_object'].make_usage_key(block_type, block_id)
        for block_type, block_id, _ in fixture['blocks']
    }
    fixture['evidence_dir'] = os.environ.get('PY36_R1_GRADING_EVIDENCE_DIR', '/edx/var/log/grading-evidence')
    return fixture


def _emit(label, payload):
    print('{} {}'.format(label, json.dumps(payload, sort_keys=True, default=text_type)))


def _redact(value):
    return re.sub(r'//[^/@]+@', '//<redacted>@', text_type(value))


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
        defaults={'activation_key': hashlib.md5(
            'p1b-grading-{}'.format(username).encode('utf8')
        ).hexdigest()},
    )
    return user


def _get_or_create_child(store, parent_location, author_id, block_type, block_id, fields):
    location = parent_location.course_key.make_usage_key(block_type, block_id)
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


def _published_fixture(fixture):
    course_key = fixture['course_key_object']
    store = modulestore()
    with store.branch_setting(ModuleStoreEnum.Branch.published_only, course_key):
        course = store.get_course(course_key)
        blocks = [store.get_item(fixture['usage_keys'][block_type]) for block_type, _, _ in fixture['blocks']]
    if course is None or course.course_status != COURSE_RELEASED_STATUS:
        raise RuntimeError('published released course is missing: {}'.format(course_key))
    if course.course_image != fixture['image_name']:
        raise RuntimeError('published course image is not gate-owned: {!r}'.format(course.course_image))
    expected_names = [display_name for _, _, display_name in fixture['blocks']]
    if [block.display_name for block in blocks] != expected_names:
        raise RuntimeError('published block names are not exact: {!r}'.format(
            [block.display_name for block in blocks]
        ))
    subsection = blocks[1]
    problem = blocks[3]
    if not subsection.graded or subsection.format != 'Homework':
        raise RuntimeError('published subsection grading metadata is incorrect')
    if problem.weight != 1.0 or problem.max_attempts is None or problem.max_attempts < 2:
        raise RuntimeError('published problem weight/attempt policy is incorrect')
    if text_type(problem.rerandomize) not in ('never', 'false'):
        raise RuntimeError('published problem randomization must be disabled')
    try:
        xml_root = etree.fromstring(problem.data.encode('utf8'))
    except (AttributeError, TypeError, etree.XMLSyntaxError) as exc:
        raise RuntimeError('published problem XML is invalid: {}'.format(exc))
    choices = xml_root.xpath('.//choicegroup/choice')
    choice_values = [text_type(''.join(choice.itertext())).strip() for choice in choices]
    correct_values = [text_type(choice.get('correct')) for choice in choices]
    if choice_values != ['GRADING_WRONG', 'GRADING_CORRECT']:
        raise RuntimeError('published choice labels are not exact: {!r}'.format(choice_values))
    if correct_values != ['false', 'true']:
        raise RuntimeError('published choice correctness is not exact: {!r}'.format(correct_values))
    if course.grading_policy != GRADING_POLICY:
        raise RuntimeError('published grading policy is not exact: {!r}'.format(course.grading_policy))
    return course, blocks


def _ensure_course(fixture, author):
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
                            'display_name': COURSE_DISPLAY_NAME,
                            'start': COURSE_START,
                            'end': COURSE_END,
                            'enrollment_start': COURSE_START,
                            'enrollment_end': COURSE_END,
                            'grading_policy': GRADING_POLICY,
                            'course_image': fixture['image_name'],
                        },
                    )
                except DuplicateCourseError:
                    pass

    with store.branch_setting(ModuleStoreEnum.Branch.draft_preferred, course_key):
        with store.bulk_operations(course_key):
            course = store.get_course(course_key)
            course.display_name = COURSE_DISPLAY_NAME
            course.start = COURSE_START
            course.end = COURSE_END
            course.enrollment_start = COURSE_START
            course.enrollment_end = COURSE_END
            course.course_image = fixture['image_name']
            course.invitation_only = False
            course.visible_to_staff_only = False
            course.course_status = COURSE_RELEASED_STATUS
            course.grading_policy = GRADING_POLICY
            parent_location = course.location
            for block_type, block_id, display_name in fixture['blocks']:
                fields = {'display_name': display_name}
                if block_type == 'sequential':
                    fields.update({'graded': True, 'format': 'Homework'})
                elif block_type == 'problem':
                    fields.update({
                        'data': PROBLEM_XML,
                        'max_attempts': 5,
                        'rerandomize': 'never',
                        'weight': 1.0,
                    })
                block = _get_or_create_child(
                    store, parent_location, author.id, block_type, block_id, fields
                )
                parent_location = block.location
            # Child creation updates the course's children in a separate read.
            # Reload before saving course metadata so a stale root cannot erase
            # the hierarchy that was just built.
            course = store.get_course(course_key)
            course.display_name = COURSE_DISPLAY_NAME
            course.start = COURSE_START
            course.end = COURSE_END
            course.enrollment_start = COURSE_START
            course.enrollment_end = COURSE_END
            course.course_image = fixture['image_name']
            course.invitation_only = False
            course.visible_to_staff_only = False
            course.course_status = COURSE_RELEASED_STATUS
            course.grading_policy = GRADING_POLICY
            course = store.update_item(course, author.id)
    store.publish(course.location, author.id)

    try:
        published_course, published_blocks = _published_fixture(fixture)
    except ItemNotFoundError:
        store.publish(course.location, author.id)
        published_course, published_blocks = _published_fixture(fixture)
    image_key = StaticContent.compute_location(course_key, fixture['image_name'])
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
    CourseOverview.load_from_module_store(course_key)
    clear_course_from_cache(course_key)
    # Publication signals enqueue these setup indexes on the default queue. The
    # grading gate intentionally consumes only grade/progress queues, so build
    # both indexes synchronously before the setup queue is purged.
    update_course_structure.apply(args=[text_type(course_key)])
    update_course_in_cache(course_key)
    return published_course, published_blocks


def _ensure_site(fixture):
    site, _ = Site.objects.get_or_create(
        domain=fixture['site_domain'],
        defaults={'name': 'P1-B grading {}'.format(fixture['runtime'])},
    )
    site.name = 'P1-B grading {}'.format(fixture['runtime'])
    site.save()
    config, _ = SiteConfiguration.objects.get_or_create(
        site=site,
        defaults={'enabled': True, 'values': {}},
    )
    values = dict(config.values or {})
    values.update({'course_org_filter': fixture['course_key_object'].org, 'ENABLE_LAST_ACTIVITY': True})
    config.enabled = True
    config.values = values
    config.save()


def _ensure_forums_disabled():
    """Keep the grading gate independent from the shared comments service."""
    config = ForumsConfig.current()
    config.enabled = False
    config.save()
    if config.enabled:
        raise RuntimeError('ForumsConfig is unexpectedly enabled')
    return config


def _ensure_completion_switch():
    switch_name = '{}.{}'.format(
        completion_waffle.WAFFLE_NAMESPACE,
        completion_waffle.ENABLE_COMPLETION_TRACKING,
    )
    switch, _ = Switch.objects.get_or_create(name=switch_name, defaults={'active': True})
    switch.active = True
    switch.save()
    if not completion_waffle.waffle().is_enabled(completion_waffle.ENABLE_COMPLETION_TRACKING):
        raise RuntimeError('completion waffle switch is not enabled through the real path')
    return switch_name


def _persistent_grades_state(fixture):
    course_key = fixture['course_key_object']
    global_flag = PersistentGradesEnabledFlag.current()
    course_flag = CoursePersistentGradesFlag.objects.filter(
        course_id=course_key,
    ).order_by('-change_date').first()
    state = {
        'global_enabled': global_flag.enabled,
        'enabled_for_all_courses': global_flag.enabled_for_all_courses,
        'course_enabled': course_flag.enabled if course_flag is not None else False,
        'effective': PersistentGradesEnabledFlag.feature_enabled(course_key),
    }
    if state != {
            'global_enabled': True,
            'enabled_for_all_courses': False,
            'course_enabled': True,
            'effective': True,
    }:
        raise RuntimeError('persistent grades configuration is invalid: {!r}'.format(state))
    return state


def _ensure_persistent_grades(fixture):
    PersistentGradesEnabledFlag.objects.create(enabled=True, enabled_for_all_courses=False)
    CoursePersistentGradesFlag.objects.create(course_id=fixture['course_key_object'], enabled=True)
    return _persistent_grades_state(fixture)


def _ensure_enrollment(fixture, learner):
    course_key = fixture['course_key_object']
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
    if enrollment is None:
        enrollment = CourseEnrollment.enroll(
            learner,
            course_key,
            mode=CourseMode.AUDIT,
            origin=EnrollmentOrigin.SELF,
        )
    else:
        enrollment.is_active = True
        enrollment.mode = CourseMode.AUDIT
        enrollment.origin = EnrollmentOrigin.SELF
        enrollment.completion_date = None
        enrollment.save()
    CourseAccessRole.objects.filter(user=learner, org=course_key.org).delete()
    if not CourseEnrollment.is_enrolled(learner, course_key):
        raise RuntimeError('learner is not actively enrolled')
    return enrollment


def _submission_filter(model, learner, course_key, problem_key):
    if model is None:
        return None
    fields = set(field.name for field in model._meta.fields)
    field_prefix = ''
    if 'student_item' in fields:
        student_item_field = model._meta.get_field('student_item')
        student_item_model = student_item_field.remote_field.model
        fields = set(field.name for field in student_item_model._meta.fields)
        field_prefix = 'student_item__'
    kwargs = {}
    if 'course_id' in fields:
        kwargs[field_prefix + 'course_id'] = text_type(course_key)
    if 'item_id' in fields:
        kwargs[field_prefix + 'item_id'] = text_type(problem_key)
    if 'item_type' in fields:
        kwargs[field_prefix + 'item_type'] = 'problem'
    if 'student_id' in fields:
        kwargs[field_prefix + 'student_id'] = anonymous_id_for_user(learner, course_key)
    elif 'anonymous_user_id' in fields:
        kwargs[field_prefix + 'anonymous_user_id'] = anonymous_id_for_user(learner, course_key)
    elif 'user_id' in fields:
        kwargs[field_prefix + 'user_id'] = learner.id
    else:
        raise RuntimeError('{} has no learner discriminator; refusing broad cleanup'.format(model.__name__))
    return kwargs


def _submission_count(model, learner, course_key, problem_key):
    filters = _submission_filter(model, learner, course_key, problem_key)
    return model.objects.filter(**filters).count() if filters else 0


def _prepare_queues():
    """Declare the isolated queue contract and discard only setup side effects."""
    from kombu import Connection

    queues = getattr(settings, 'GRADING_QUEUES', {})
    exchange_name = settings.CELERY_DEFAULT_EXCHANGE
    purged = {}
    connection = Connection(settings.BROKER_URL, connect_timeout=3)
    with connection as conn:
        channel = conn.channel()
        channel.exchange_declare(exchange=exchange_name, type='direct', durable=True, auto_delete=False)
        for role, queue in queues.items():
            channel.queue_declare(queue=queue, durable=True, auto_delete=False)
            channel.queue_bind(queue=queue, exchange=exchange_name, routing_key=queue)
            if role not in ('grade', 'progress'):
                purged[role] = channel.queue_purge(queue=queue)
        channel.close()
    return purged


def _row_counts(fixture, learner):
    course_key = fixture['course_key_object']
    problem_key = fixture['usage_keys']['problem']
    subsection_key = fixture['usage_keys']['sequential']
    enrollment = CourseEnrollment.objects.filter(user=learner, course_id=course_key).first()
    grade = PersistentSubsectionGrade.objects.filter(
        user_id=learner.id, course_id=course_key, usage_key=subsection_key,
    ).first()
    return {
        'student_module': StudentModule.objects.filter(
            student=learner, course_id=course_key, module_state_key=problem_key,
        ).count(),
        'block_completion': BlockCompletion.objects.filter(
            user=learner, course_key=course_key, block_key=problem_key,
        ).count(),
        'subsection_grade': PersistentSubsectionGrade.objects.filter(
            user_id=learner.id, course_id=course_key, usage_key=subsection_key,
        ).count(),
        'course_grade': PersistentCourseGrade.objects.filter(
            user_id=learner.id, course_id=course_key,
        ).count(),
        'course_progress': PersistentCourseProgress.objects.filter(
            user_id=learner.id, course_id=course_key,
        ).count(),
        'subsection_override': PersistentSubsectionGradeOverride.objects.filter(
            grade__user_id=learner.id, grade__course_id=course_key,
        ).count(),
        'submissions_submission': _submission_count(Submission, learner, course_key, problem_key),
        'submissions_score': _submission_count(SubmissionScore, learner, course_key, problem_key),
        'certificates': GeneratedCertificate.objects.filter(user=learner, course_id=course_key).count(),
        'enrollment': 1 if enrollment is not None and enrollment.is_active else 0,
        'enrollment_completion_date': (
            text_type(enrollment.completion_date)
            if enrollment is not None and enrollment.completion_date is not None else None
        ),
        'learner_id': learner.id,
        'subsection_grade_row': grade,
    }


def _queue_snapshot():
    queues = getattr(settings, 'GRADING_QUEUES', {})
    result = {}
    try:
        from kombu import Connection
        connection = Connection(settings.BROKER_URL, connect_timeout=3)
        with connection as conn:
            channel = conn.channel()
            for role, queue in queues.items():
                try:
                    declared = channel.queue_declare(queue=queue, passive=True)
                    result[role] = {
                        'queue': queue,
                        'messages_ready': declared.message_count,
                        'consumers': declared.consumer_count,
                    }
                except Exception as exc:  # pragma: no cover - broker-specific failure path
                    result[role] = {'queue': queue, 'error': _redact(text_type(exc))}
            channel.close()
    except Exception as exc:  # pragma: no cover - broker-specific failure path
        result['broker_error'] = _redact(text_type(exc))
    return result


def _worker_snapshot():
    try:
        from lms.celery import APP
        inspector = APP.control.inspect(timeout=3)
        registered = inspector.registered() or {}
        ping = APP.control.ping(timeout=3) or []
        active = inspector.active() or {}
        reserved = inspector.reserved() or {}
        scheduled = inspector.scheduled() or {}
        names = sorted(set(
            text_type(name).split(' [', 1)[0]
            for values in registered.values() for name in values
        ))
        required = [
            'lms.djangoapps.grades.tasks.recalculate_subsection_grade_v3',
            'lms.djangoapps.grades.tasks.calculate_course_progress',
        ]
        return {
            'ping': ping,
            'registered_required': {name: name in names for name in required},
            'registered_count': len(names),
            'active': active,
            'reserved': reserved,
            'scheduled': scheduled,
        }
    except Exception as exc:  # pragma: no cover - worker-specific failure path
        return {'error': _redact(text_type(exc))}


def _task_log_summary(fixture):
    log_path = os.environ.get('PY36_R1_GRADING_WORKER_LOG', '/edx/var/log/worker.log')
    try:
        with open(log_path, 'r') as log_file:
            content = log_file.read()
    except IOError as exc:
        return {'path': log_path, 'error': text_type(exc)}
    names = {
        'grade': 'lms.djangoapps.grades.tasks.recalculate_subsection_grade_v3',
        'progress': 'lms.djangoapps.grades.tasks.calculate_course_progress',
    }
    summary = {'path': log_path}
    attempt = int(os.environ.get('PY36_R1_GRADING_ATTEMPT', '1'))
    for role, task_name in names.items():
        pattern = re.escape(task_name)
        received = re.findall(
            r'^(\d{4}-\d{2}-\d{2} [^ ]+).*Received task: %s\[([^\]]+)\]' % pattern,
            content,
            re.MULTILINE,
        )
        succeeded = re.findall(
            r'^(\d{4}-\d{2}-\d{2} [^ ]+).*Task %s\[([^\]]+)\] succeeded' % pattern,
            content,
            re.MULTILINE,
        )
        retry = re.findall(
            r'^(\d{4}-\d{2}-\d{2} [^ ]+).*%s\[([^\]]+)\].*(?:retry|Retry)' % pattern,
            content,
            re.MULTILINE,
        )
        expected = attempt * (2 if role == 'grade' else 1)
        summary[role] = {
            'task_name': task_name,
            'successes': len(succeeded),
            'received_records': len(received),
            'retry_records': len(retry),
            'received': [{'timestamp': timestamp, 'task_id': task_id} for timestamp, task_id in received],
            'succeeded': [{'timestamp': timestamp, 'task_id': task_id} for timestamp, task_id in succeeded],
            'task_ids': sorted(set(task_id for _, task_id in received + succeeded)),
            'expected_cumulative_successes': expected,
        }
    return summary


def _assert_idle(snapshot):
    for role, item in snapshot.items():
        if role == 'broker_error' or item.get('error'):
            raise RuntimeError('queue snapshot failed for {}: {!r}'.format(role, item))
        if item.get('messages_ready') != 0:
            raise RuntimeError('queue is not idle for {}: {!r}'.format(role, item))
        if role in ('grade', 'progress') and item.get('consumers') != 1:
            raise RuntimeError('grading queue consumer count is invalid for {}: {!r}'.format(role, item))


def _assert_worker_idle(snapshot):
    if snapshot.get('error'):
        raise RuntimeError('worker snapshot failed: {!r}'.format(snapshot))
    if len(snapshot.get('ping', [])) != 1:
        raise RuntimeError('grading worker ping count is not exactly one: {!r}'.format(snapshot.get('ping')))
    for state_name in ('active', 'reserved', 'scheduled'):
        task_lists = snapshot.get(state_name, {})
        if any(tasks for tasks in task_lists.values()):
            raise RuntimeError('grading worker is not idle in {}: {!r}'.format(state_name, task_lists))


def _assert_task_summary(summary, attempt, phase):
    expected_counts = {
        'midcondition': {'grade': attempt * 2 - 1, 'progress': attempt},
        'postflight': {'grade': attempt * 2, 'progress': attempt},
    }
    expected = expected_counts[phase]
    for role, expected_count in expected.items():
        role_summary = summary.get(role, {})
        received_ids = [item['task_id'] for item in role_summary.get('received', [])]
        succeeded_ids = [item['task_id'] for item in role_summary.get('succeeded', [])]
        if (
                role_summary.get('received_records') != expected_count or
                role_summary.get('successes') != expected_count or
                role_summary.get('retry_records') != 0 or
                len(set(received_ids)) != expected_count or
                set(received_ids) != set(succeeded_ids)
        ):
            raise RuntimeError('{} task summary is not exact for {}: {!r}'.format(
                phase, role, role_summary
            ))


def _assert_zero_precondition(counts):
    zero_fields = (
        'student_module', 'block_completion', 'subsection_grade', 'course_grade',
        'course_progress', 'subsection_override', 'submissions_submission',
        'submissions_score', 'certificates',
    )
    nonzero = {name: counts[name] for name in zero_fields if counts[name] != 0}
    if nonzero:
        raise RuntimeError('gate-owned precondition rows remain: {!r}'.format(nonzero))
    if counts['enrollment'] != 1 or counts['enrollment_completion_date'] is not None:
        raise RuntimeError('active audit enrollment/completion precondition is invalid: {!r}'.format(counts))


def provision(fixture):
    author = _get_or_create_user(fixture['author'], fixture['author_email'], True)
    learner = _get_or_create_user(fixture['username'], fixture['email'], False)
    persistent_grades = _ensure_persistent_grades(fixture)
    published_course, published_blocks = _ensure_course(fixture, author)
    purged_queues = _prepare_queues()
    _ensure_site(fixture)
    forums_config = _ensure_forums_disabled()
    switch_name = _ensure_completion_switch()
    enrollment = _ensure_enrollment(fixture, learner)
    counts = _row_counts(fixture, learner)
    _assert_zero_precondition(counts)
    _emit('PROVISION_OK', {
        'runtime': fixture['runtime'],
        'namespace': fixture['namespace'],
        'user_id': learner.id,
        'username': learner.username,
        'course_key': text_type(fixture['course_key_object']),
        'published_usage_keys': [text_type(block.location) for block in published_blocks],
        'course_status': published_course.course_status,
        'grading_policy': published_course.grading_policy,
        'persistent_grades': persistent_grades,
        'completion_switch': switch_name,
        'completion_switch_active': True,
        'forums': {
            'enabled': forums_config.enabled,
            'connection_timeout': forums_config.connection_timeout,
        },
        'enrollment': {
            'active': enrollment.is_active,
            'mode': enrollment.mode,
            'origin': enrollment.origin,
            'completion_date': enrollment.completion_date,
        },
        'row_counts': {key: value for key, value in counts.items() if key != 'subsection_grade_row'},
        'purged_setup_queues': purged_queues,
        'site_domain': fixture['site_domain'],
    })


def preflight(fixture):
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    if learner.is_staff or learner.is_superuser or not learner.is_active:
        raise RuntimeError('learner privilege/active state is invalid')
    course, blocks = _published_fixture(fixture)
    overview = CourseOverview.load_from_module_store(fixture['course_key_object'])
    if overview.course_status != COURSE_RELEASED_STATUS:
        raise RuntimeError('course overview is not released')
    forums_config = ForumsConfig.current()
    if forums_config.enabled:
        raise RuntimeError('ForumsConfig must be disabled for the grading gate')
    if not _ensure_completion_switch():
        raise RuntimeError('completion switch was not enabled')
    persistent_grades = _persistent_grades_state(fixture)
    enrollment = _ensure_enrollment(fixture, learner)
    counts = _row_counts(fixture, learner)
    _assert_zero_precondition(counts)
    queue_state = _queue_snapshot()
    _assert_idle(queue_state)
    worker_state = _worker_snapshot()
    required = worker_state.get('registered_required', {})
    if worker_state.get('error') or not all(required.values()):
        raise RuntimeError('worker registration/ping is invalid: {!r}'.format(worker_state))
    _assert_worker_idle(worker_state)
    _emit('PRECONDITION_OK', {
        'runtime': fixture['runtime'],
        'namespace': fixture['namespace'],
        'username': learner.username,
        'user_id': learner.id,
        'course_key': text_type(fixture['course_key_object']),
        'published_usage_keys': [text_type(block.location) for block in blocks],
        'problem_id': text_type(fixture['usage_keys']['problem']),
        'subsection_key': text_type(fixture['usage_keys']['sequential']),
        'course_status': course.course_status,
        'grading_policy': course.grading_policy,
        'grading_policy_hash': GradesTransformer.grading_policy_hash(course),
        'persistent_grades': persistent_grades,
        'forums': {
            'enabled': forums_config.enabled,
            'connection_timeout': forums_config.connection_timeout,
        },
        'enrollment': {
            'active': enrollment.is_active,
            'mode': enrollment.mode,
            'origin': enrollment.origin,
            'completion_date': enrollment.completion_date,
        },
        'privileges': {'is_staff': learner.is_staff, 'is_superuser': learner.is_superuser, 'course_roles': []},
        'row_counts': {key: value for key, value in counts.items() if key != 'subsection_grade_row'},
        'queue_state': queue_state,
        'worker_state': worker_state,
        'broker': {
            'host': getattr(settings, 'RABBIT_CONTAINER', None),
            'port': 5672,
            'vhost': getattr(settings, 'RABBIT_VHOST', None),
            'user': getattr(settings, 'RABBIT_USER', None),
            'password_configured': bool(getattr(settings, 'RABBIT_PASSWORD', None)),
            'queues': getattr(settings, 'GRADING_QUEUES', {}),
        },
        'cache': settings.CACHES.get('default'),
        'sql': {key: value.get('NAME') for key, value in settings.DATABASES.items()},
        'mongo': {
            'module_store': settings.MODULESTORE['default']['OPTIONS']['stores'][0]['DOC_STORE_CONFIG'].get('db'),
            'content_store': settings.CONTENTSTORE.get('DOC_STORE_CONFIG', {}).get('db') if settings.CONTENTSTORE else None,
        },
        'celery_always_eager': settings.CELERY_ALWAYS_EAGER,
        'site_domain': fixture['site_domain'],
    })


def reset(fixture):
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    course_key = fixture['course_key_object']
    problem_key = fixture['usage_keys']['problem']
    subsection_key = fixture['usage_keys']['sequential']
    enrollment = CourseEnrollment.objects.filter(user=learner, course_id=course_key).first()
    if enrollment is None or not enrollment.is_active or enrollment.mode != CourseMode.AUDIT:
        raise RuntimeError('refusing reset without retained active audit enrollment')
    if learner.is_staff or learner.is_superuser:
        raise RuntimeError('refusing reset for privileged learner')
    PersistentSubsectionGradeOverride.objects.filter(
        grade__user_id=learner.id, grade__course_id=course_key,
    ).delete()
    StudentModule.objects.filter(
        student=learner, course_id=course_key, module_state_key=problem_key,
    ).delete()
    BlockCompletion.objects.filter(user=learner, course_key=course_key, block_key=problem_key).delete()
    PersistentSubsectionGrade.objects.filter(
        user_id=learner.id, course_id=course_key, usage_key=subsection_key,
    ).delete()
    PersistentCourseGrade.objects.filter(user_id=learner.id, course_id=course_key).delete()
    PersistentCourseProgress.objects.filter(user_id=learner.id, course_id=course_key).delete()
    if Submission is not None:
        submission_filter = _submission_filter(Submission, learner, course_key, problem_key)
        Submission.objects.filter(**submission_filter).delete()
    if SubmissionScore is not None:
        score_filter = _submission_filter(SubmissionScore, learner, course_key, problem_key)
        SubmissionScore.objects.filter(**score_filter).delete()
    GeneratedCertificate.objects.filter(user=learner, course_id=course_key).delete()
    enrollment.completion_date = None
    enrollment.save(update_fields=['completion_date'])
    clear_course_from_cache(course_key)
    counts = _row_counts(fixture, learner)
    _assert_zero_precondition(counts)
    _emit('RESET_OK', {
        'runtime': fixture['runtime'],
        'namespace': fixture['namespace'],
        'username': learner.username,
        'course_key': text_type(course_key),
        'preserved_course': True,
        'preserved_learner': True,
        'preserved_enrollment': True,
        'row_counts': {key: value for key, value in counts.items() if key != 'subsection_grade_row'},
        'queue_state': _queue_snapshot(),
    })
    preflight(fixture)


def _write_evidence(fixture, name, payload):
    evidence_dir = fixture['evidence_dir']
    if not os.path.isdir(evidence_dir):
        os.makedirs(evidence_dir)
    path = os.path.join(evidence_dir, name)
    with open(path, 'w') as evidence_file:
        evidence_file.write(json.dumps(payload, sort_keys=True, default=text_type))
    return path


def midcondition(fixture):
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    course_key = fixture['course_key_object']
    problem_key = fixture['usage_keys']['problem']
    subsection_key = fixture['usage_keys']['sequential']
    student_modules = list(StudentModule.objects.filter(
        student=learner, course_id=course_key, module_state_key=problem_key,
    ))
    completions = list(BlockCompletion.objects.filter(user=learner, course_key=course_key, block_key=problem_key))
    subsection_grades = list(PersistentSubsectionGrade.objects.filter(
        user_id=learner.id, course_id=course_key, usage_key=subsection_key,
    ))
    course_grades = list(PersistentCourseGrade.objects.filter(user_id=learner.id, course_id=course_key))
    progresses = list(PersistentCourseProgress.objects.filter(user_id=learner.id, course_id=course_key))
    enrollment = CourseEnrollment.objects.get(user=learner, course_id=course_key)
    if len(student_modules) != 1 or student_modules[0].grade != 0 or student_modules[0].max_grade != 1:
        raise RuntimeError('midcondition StudentModule is not exactly 0/1: {!r}'.format(student_modules))
    state = json.loads(student_modules[0].state or '{}')
    if state.get('attempts') != 1:
        raise RuntimeError('midcondition attempt count is not one: {!r}'.format(state))
    if len(completions) != 1 or completions[0].completion != 1.0:
        raise RuntimeError('midcondition completion is not exactly 1.0')
    if len(subsection_grades) != 1 or subsection_grades[0].earned_graded != 0 or subsection_grades[0].possible_graded != 1:
        raise RuntimeError('midcondition subsection grade is not exactly 0/1')
    if len(course_grades) != 1 or course_grades[0].percent_grade != 0 or course_grades[0].passed_timestamp is not None:
        raise RuntimeError('midcondition course grade is not non-passing 0.0')
    if len(progresses) != 1 or progresses[0].percent_progress != 1.0:
        raise RuntimeError('midcondition course progress is not exactly 1.0')
    if enrollment.completion_date is None:
        raise RuntimeError('midcondition enrollment completion date is missing')
    attempt = int(os.environ.get('PY36_R1_GRADING_ATTEMPT', '1'))
    queue_state = _queue_snapshot()
    worker_state = _worker_snapshot()
    task_summary = _task_log_summary(fixture)
    _assert_idle(queue_state)
    _assert_worker_idle(worker_state)
    _assert_task_summary(task_summary, attempt, 'midcondition')
    payload = {
        'runtime': fixture['runtime'],
        'attempt': attempt,
        'namespace': fixture['namespace'],
        'username': learner.username,
        'course_key': text_type(course_key),
        'problem_key': text_type(problem_key),
        'subsection_key': text_type(subsection_key),
        'student_module': {'id': student_modules[0].id, 'grade': student_modules[0].grade,
                           'max_grade': student_modules[0].max_grade, 'attempts': state.get('attempts')},
        'block_completion': {'id': completions[0].id, 'completion': completions[0].completion},
        'subsection_grade': {'id': subsection_grades[0].id, 'earned_graded': subsection_grades[0].earned_graded,
                             'possible_graded': subsection_grades[0].possible_graded},
        'course_grade': {'id': course_grades[0].id, 'percent_grade': course_grades[0].percent_grade,
                         'letter_grade': course_grades[0].letter_grade, 'passed_timestamp': course_grades[0].passed_timestamp},
        'course_progress': {'id': progresses[0].id, 'percent_progress': progresses[0].percent_progress},
        'enrollment_completion_date': enrollment.completion_date,
        'queue_state': queue_state,
        'worker_state': worker_state,
        'task_summary': task_summary,
    }
    _write_evidence(fixture, 'midcondition.json', payload)
    _write_evidence(fixture, 'midcondition.release', {
        'status': 'MIDCONDITION_OK',
        'runtime': fixture['runtime'],
        'attempt': attempt,
    })
    _emit('MIDCONDITION_OK', payload)


def _contains_value(value, needle):
    if isinstance(value, dict):
        return any(_contains_value(key, needle) or _contains_value(item, needle) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_value(item, needle) for item in value)
    return text_type(value) == needle


def postflight(fixture):
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    course_key = fixture['course_key_object']
    problem_key = fixture['usage_keys']['problem']
    subsection_key = fixture['usage_keys']['sequential']
    modules = list(StudentModule.objects.filter(student=learner, course_id=course_key, module_state_key=problem_key))
    completions = list(BlockCompletion.objects.filter(user=learner, course_key=course_key, block_key=problem_key))
    subsection_grades = list(PersistentSubsectionGrade.objects.filter(
        user_id=learner.id, course_id=course_key, usage_key=subsection_key,
    ))
    course_grades = list(PersistentCourseGrade.objects.filter(user_id=learner.id, course_id=course_key))
    progresses = list(PersistentCourseProgress.objects.filter(user_id=learner.id, course_id=course_key))
    enrollment = CourseEnrollment.objects.get(user=learner, course_id=course_key)
    course, blocks = _published_fixture(fixture)
    if len(modules) != 1 or modules[0].grade != 1 or modules[0].max_grade != 1:
        raise RuntimeError('postflight StudentModule is not exactly 1/1')
    module_state = json.loads(modules[0].state or '{}')
    if (
            module_state.get('attempts') != 2 or
            not _contains_value(module_state.get('student_answers', {}), 'choice_1') or
            not _contains_value(module_state.get('correct_map', {}), 'correct')
    ):
        raise RuntimeError('postflight StudentModule state lacks two attempts/correct answer: {!r}'.format(module_state))
    if len(completions) != 1 or completions[0].completion != 1.0:
        raise RuntimeError('postflight completion row is not exactly one 1.0 row')
    if len(subsection_grades) != 1 or subsection_grades[0].earned_graded != 1 or subsection_grades[0].possible_graded != 1:
        raise RuntimeError('postflight subsection grade is not exactly 1/1')
    if subsection_grades[0].first_attempted is None:
        raise RuntimeError('postflight subsection first_attempted is missing')
    if len(course_grades) != 1 or course_grades[0].percent_grade != 1.0 or course_grades[0].letter_grade != 'Pass':
        raise RuntimeError('postflight course grade is not exactly Pass 1.0')
    if course_grades[0].passed_timestamp is None:
        raise RuntimeError('postflight course grade passed timestamp is missing')
    expected_policy_hash = GradesTransformer.grading_policy_hash(course)
    if course_grades[0].grading_policy_hash != expected_policy_hash:
        raise RuntimeError('postflight grading policy hash mismatch')
    if len(progresses) != 1 or progresses[0].percent_progress != 1.0:
        raise RuntimeError('postflight course progress is not exactly 1.0')
    if not enrollment.is_active or enrollment.mode != CourseMode.AUDIT or enrollment.origin != EnrollmentOrigin.SELF:
        raise RuntimeError('postflight enrollment is not active audit self enrollment')
    if enrollment.completion_date is None:
        raise RuntimeError('postflight enrollment completion date is missing')
    midcondition_path = os.path.join(fixture['evidence_dir'], 'midcondition.json')
    if os.path.exists(midcondition_path):
        with open(midcondition_path, 'r') as mid_file:
            mid_payload = json.load(mid_file)
        if text_type(enrollment.completion_date) != text_type(mid_payload['enrollment_completion_date']):
            raise RuntimeError('completion timestamp moved between wrong and correct transitions')
    if _submission_count(Submission, learner, course_key, problem_key) != 0 or _submission_count(
            SubmissionScore, learner, course_key, problem_key) != 0:
        raise RuntimeError('CAPA problem unexpectedly created Submissions API rows')
    if GeneratedCertificate.objects.filter(user=learner, course_id=course_key).exists():
        raise RuntimeError('certificate side effect exists')
    queue_state = _queue_snapshot()
    _assert_idle(queue_state)
    worker_state = _worker_snapshot()
    _assert_worker_idle(worker_state)
    task_summary = _task_log_summary(fixture)
    attempt = int(os.environ.get('PY36_R1_GRADING_ATTEMPT', '1'))
    _assert_task_summary(task_summary, attempt, 'postflight')
    payload = {
        'runtime': fixture['runtime'],
        'attempt': attempt,
        'namespace': fixture['namespace'],
        'username': learner.username,
        'course_key': text_type(course_key),
        'problem_key': text_type(problem_key),
        'subsection_key': text_type(subsection_key),
        'published_usage_keys': [text_type(block.location) for block in blocks],
        'student_module': {'id': modules[0].id, 'grade': modules[0].grade, 'max_grade': modules[0].max_grade,
                           'attempts': module_state.get('attempts'), 'state': module_state},
        'block_completion': {'id': completions[0].id, 'completion': completions[0].completion},
        'subsection_grade': {'id': subsection_grades[0].id, 'earned_graded': subsection_grades[0].earned_graded,
                             'possible_graded': subsection_grades[0].possible_graded,
                             'first_attempted': subsection_grades[0].first_attempted},
        'course_grade': {'id': course_grades[0].id, 'percent_grade': course_grades[0].percent_grade,
                         'letter_grade': course_grades[0].letter_grade,
                         'passed_timestamp': course_grades[0].passed_timestamp,
                         'grading_policy_hash': course_grades[0].grading_policy_hash},
        'course_progress': {'id': progresses[0].id, 'percent_progress': progresses[0].percent_progress},
        'enrollment': {'active': enrollment.is_active, 'mode': enrollment.mode, 'origin': enrollment.origin,
                       'completion_date': enrollment.completion_date},
        'submissions_submission': _submission_count(Submission, learner, course_key, problem_key),
        'submissions_score': _submission_count(SubmissionScore, learner, course_key, problem_key),
        'certificates': 0,
        'queue_state': queue_state,
        'worker_state': worker_state,
        'task_summary': task_summary,
    }
    _write_evidence(fixture, 'postflight.json', payload)
    _emit('POSTCONDITION_OK', payload)


def main():
    actions = ('provision', 'preflight', 'reset', 'midcondition', 'postflight')
    if len(sys.argv) != 2 or sys.argv[1] not in actions:
        raise SystemExit('usage: {} {{{}}}'.format(sys.argv[0], '|'.join(actions)))
    fixture = _fixture()
    globals()[sys.argv[1]](fixture)


if __name__ == '__main__':
    main()
