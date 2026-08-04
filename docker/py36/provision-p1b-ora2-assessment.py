# -*- coding: utf-8 -*-
"""Provision, reset, and verify the disposable P1-B ORA2 assessment gate."""
from __future__ import absolute_import, division, print_function, unicode_literals

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

import django
import pkg_resources
import pytz
from six import text_type

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.contrib.sites.models import Site  # noqa: E402
from waffle.models import Switch  # noqa: E402

from completion import waffle as completion_waffle  # noqa: E402
from completion.models import BlockCompletion  # noqa: E402
from course_modes.models import CourseMode  # noqa: E402
from courseware.models import StudentModule  # noqa: E402
from django_comment_common.models import ForumsConfig  # noqa: E402
from lms.djangoapps.certificates.models import GeneratedCertificate  # noqa: E402
from lms.djangoapps.grades.config.models import (  # noqa: E402
    CoursePersistentGradesFlag,
    PersistentGradesEnabledFlag,
)
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
from student.roles import CourseStaffRole  # noqa: E402
from submissions.models import (  # noqa: E402
    Score,
    ScoreAnnotation,
    ScoreSummary,
    StudentItem,
    Submission,
)
from xmodule.contentstore.content import StaticContent  # noqa: E402
from xmodule.contentstore.django import contentstore  # noqa: E402
from xmodule.course_module import COURSE_RELEASED_STATUS  # noqa: E402
from xmodule.modulestore import ModuleStoreEnum  # noqa: E402
from xmodule.modulestore.django import modulestore  # noqa: E402
from xmodule.modulestore.exceptions import DuplicateCourseError, ItemNotFoundError  # noqa: E402

from openassessment.assessment.models import (  # noqa: E402
    Assessment,
    AssessmentPart,
    Criterion,
    CriterionOption,
    Rubric,
    StaffWorkflow,
)
from openassessment.workflow.models import (  # noqa: E402
    AssessmentWorkflow,
    AssessmentWorkflowCancellation,
    AssessmentWorkflowStep,
)
from openassessment.xblock.staff_area_mixin import StaffAreaMixin  # noqa: E402
from openassessment.xblock.staff_assessment_mixin import StaffAssessmentMixin  # noqa: E402
from openassessment.xblock.xml import serialize_content  # noqa: E402


EXPECTED_PLATFORM_COMMIT = '7644241bb598ac20e20e70dd7abf2e5110f5b7bd'
EXPECTED_PLATFORM_TREE = '7c5e963e767bb1eaa16c9e64222694698b7727a3'
EXPECTED_ORA2_COMMIT = 'd3f24a9c539528e960c8dcc9aef200cea0c49baf'
COURSE_DISPLAY_NAME = 'P1-B ORA2 Assessment'
COURSE_START = datetime(2026, 8, 1, tzinfo=pytz.UTC)
COURSE_END = datetime(2027, 8, 1, tzinfo=pytz.UTC)
SUBMISSION_START = '2001-01-01T00:00'
SUBMISSION_DUE = '2029-01-01T00:00'
PROMPT = 'Enter a response containing the exact ORA2 gate marker.'
PASSWORD = 'P1bOra2AssessmentR1!'
RUBRIC_CRITERIA = [{
    'name': 'response_quality',
    'label': 'Response quality',
    'prompt': 'Evaluate whether the response includes the required gate marker.',
    'order_num': 0,
    'feedback': 'disabled',
    'options': [
        {
            'name': 'needs_revision',
            'label': 'Needs revision',
            'explanation': 'The required gate marker is missing.',
            'points': 0,
            'order_num': 0,
        },
        {
            'name': 'meets_requirement',
            'label': 'Meets requirement',
            'explanation': 'The response includes the required gate marker.',
            'points': 2,
            'order_num': 1,
        },
    ],
}]
RUBRIC_ASSESSMENTS = [{
    'name': 'staff-assessment',
    'start': SUBMISSION_START,
    'due': SUBMISSION_DUE,
    'required': True,
}]
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
    ('chapter', 'ora2_section', 'ORA2 Section'),
    ('sequential', 'ora2_subsection', 'ORA2 Subsection'),
    ('vertical', 'ora2_unit', 'ORA2 Unit'),
)
RUNTIME_FIXTURES = {
    'py36': {
        'username': 'qaora2_py36',
        'email': 'qaora2_py36@example.com',
        'staff_username': 'qaora2staff_py36',
        'staff_email': 'qaora2staff_py36@example.com',
        'author': 'qaora2author_py36',
        'author_email': 'qaora2author_py36@example.com',
        'course_key': 'course-v1:QA+ORA2Assessment+Py36',
        'ora2_id': 'p1b_ora2_staff_py36',
        'namespace': 'py36_r1_p1b_ora2_assessment_py36_r17',
        'site_domain': 'localhost:18145',
        'image_name': 'p1b_ora2_assessment_py36_r17.jpg',
        'submissions_version': '2.1.1',
    },
    'py27': {
        'username': 'qaora2_py27',
        'email': 'qaora2_py27@example.com',
        'staff_username': 'qaora2staff_py27',
        'staff_email': 'qaora2staff_py27@example.com',
        'author': 'qaora2author_py27',
        'author_email': 'qaora2author_py27@example.com',
        'course_key': 'course-v1:QA+ORA2Assessment+Py27',
        'ora2_id': 'p1b_ora2_staff_py27',
        'namespace': 'py36_r1_p1b_ora2_assessment_py27_r2',
        'site_domain': 'localhost:18146',
        'image_name': 'p1b_ora2_assessment_py27_r2.jpg',
        'submissions_version': '2.0.12',
    },
}


def _blocks(fixture):
    return BASE_BLOCKS + (('openassessment', fixture['ora2_id'], 'ORA2 Staff Checkpoint'),)


def _fixture():
    runtime = os.environ.get('PY36_R1_ORA2_RUNTIME')
    if runtime not in RUNTIME_FIXTURES:
        raise RuntimeError('PY36_R1_ORA2_RUNTIME must be py36 or py27')
    fixture = dict(RUNTIME_FIXTURES[runtime])
    fixture['runtime'] = runtime
    expected = {
        'username': 'PY36_R1_ORA2_USERNAME',
        'email': 'PY36_R1_ORA2_EMAIL',
        'staff_username': 'PY36_R1_ORA2_STAFF_USERNAME',
        'staff_email': 'PY36_R1_ORA2_STAFF_EMAIL',
        'course_key': 'PY36_R1_ORA2_COURSE_KEY',
        'namespace': 'PY36_R1_ORA2_NAMESPACE',
        'site_domain': 'PY36_R1_ORA2_SITE_DOMAIN',
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
        for block_type, block_id, _display_name in fixture['blocks']
    }
    fixture['attempt'] = int(os.environ.get('PY36_R1_ORA2_ATTEMPT', '1'))
    if fixture['attempt'] not in (1, 2):
        raise RuntimeError('PY36_R1_ORA2_ATTEMPT must be 1 or 2')
    fixture['response_marker'] = os.environ.get(
        'PY36_R1_ORA2_RESPONSE_MARKER',
        'ORA2_RESPONSE_{}_A{}'.format(runtime, fixture['attempt']),
    )
    fixture['feedback_marker'] = os.environ.get(
        'PY36_R1_ORA2_FEEDBACK_MARKER',
        'ORA2_FEEDBACK_{}_A{}'.format(runtime, fixture['attempt']),
    )
    fixture['evidence_dir'] = os.environ.get(
        'PY36_R1_ORA2_EVIDENCE_DIR', '/edx/var/log/ora2-evidence'
    )
    fixture['worker_log'] = os.environ.get('PY36_R1_ORA2_WORKER_LOG', '/edx/var/log/worker.log')
    fixture['lms_log'] = os.environ.get('PY36_R1_ORA2_LMS_LOG', '/edx/var/log/lms.log')
    fixture['handshake_dir'] = os.environ.get(
        'PY36_R1_ORA2_HANDSHAKE_DIR', '/edx/var/log/handshakes'
    )
    return fixture


def _emit(label, payload):
    print('{} {}'.format(label, json.dumps(payload, sort_keys=True, default=text_type)))


def _redact(value):
    return re.sub(r'//[^/@]+@', '//<redacted>@', text_type(value))


def _get_or_create_user(username, email, privileged=False):
    user, _created = User.objects.get_or_create(username=username, defaults={'email': email})
    user.email = email
    user.is_active = True
    user.is_staff = privileged
    user.is_superuser = privileged
    user.set_password(PASSWORD)
    user.save()
    profile, _created = UserProfile.objects.get_or_create(user=user, defaults={'name': username})
    profile.name = username
    profile.save()
    Registration.objects.get_or_create(
        user=user,
        defaults={'activation_key': hashlib.md5(
            'p1b-ora2-{}'.format(username).encode('utf8')
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


def _ora2_fields():
    return {
        'display_name': 'ORA2 Staff Checkpoint',
        'title': 'ORA2 Staff Checkpoint',
        'prompt': PROMPT,
        'prompts_type': 'text',
        'rubric_criteria': RUBRIC_CRITERIA,
        'rubric_assessments': RUBRIC_ASSESSMENTS,
        'rubric_feedback_prompt': 'Provide the exact ORA2 feedback marker.',
        'rubric_feedback_default_text': '',
        'submission_start': SUBMISSION_START,
        'submission_due': SUBMISSION_DUE,
        'text_response_raw': 'required',
        'file_upload_response_raw': None,
        'file_upload_type_raw': None,
        'allow_file_upload': False,
        'allow_latex': False,
        'leaderboard_show': 0,
        'group_access': {},
        'weight': 1.0,
        'start': COURSE_START,
        'due': COURSE_END,
    }


def _published_fixture(fixture):
    course_key = fixture['course_key_object']
    store = modulestore()
    with store.branch_setting(ModuleStoreEnum.Branch.published_only, course_key):
        course = store.get_course(course_key)
        blocks = [store.get_item(fixture['usage_keys'][block_type]) for block_type, _id, _name in fixture['blocks']]
    if course is None or course.course_status != COURSE_RELEASED_STATUS:
        raise RuntimeError('published released course is missing: {}'.format(course_key))
    if course.course_image != fixture['image_name']:
        raise RuntimeError('published course image is not gate-owned: {!r}'.format(course.course_image))
    expected_names = [display_name for _block_type, _block_id, display_name in fixture['blocks']]
    if [block.display_name for block in blocks] != expected_names:
        raise RuntimeError('published block names are not exact: {!r}'.format(
            [block.display_name for block in blocks]
        ))
    subsection = blocks[1]
    ora2_block = blocks[3]
    if not subsection.graded or subsection.format != 'Homework':
        raise RuntimeError('published ORA2 subsection grading metadata is incorrect')
    if ora2_block.weight != 1.0:
        raise RuntimeError('published ORA2 block weight is not 1.0')
    if ora2_block.prompt != PROMPT or ora2_block.prompts_type != 'text':
        raise RuntimeError('published ORA2 prompt is not exact')
    if ora2_block.rubric_criteria != RUBRIC_CRITERIA:
        raise RuntimeError('published ORA2 rubric criteria are not exact: {!r}'.format(ora2_block.rubric_criteria))
    if ora2_block.rubric_assessments != RUBRIC_ASSESSMENTS:
        raise RuntimeError('published ORA2 assessment steps are not exact: {!r}'.format(
            ora2_block.rubric_assessments
        ))
    if (
            ora2_block.text_response != 'required' or
            ora2_block.file_upload_response is not None or
            ora2_block.file_upload_type is not None or
            ora2_block.allow_file_upload
    ):
        raise RuntimeError('published ORA2 response type is not text-only required')
    if course.grading_policy != GRADING_POLICY:
        raise RuntimeError('published ORA2 grading policy is not exact: {!r}'.format(course.grading_policy))
    olx = serialize_content(ora2_block)
    return course, blocks, olx


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
                            'advanced_modules': ['openassessment'],
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
            course.advanced_modules = ['openassessment']
            parent_location = course.location
            for block_type, block_id, display_name in fixture['blocks']:
                fields = {'display_name': display_name}
                if block_type == 'sequential':
                    fields.update({'graded': True, 'format': 'Homework'})
                elif block_type == 'openassessment':
                    fields.update(_ora2_fields())
                block = _get_or_create_child(
                    store, parent_location, author.id, block_type, block_id, fields
                )
                parent_location = block.location
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
            course.advanced_modules = ['openassessment']
            course = store.update_item(course, author.id)
    store.publish(course.location, author.id)

    try:
        published_course, published_blocks, olx = _published_fixture(fixture)
    except ItemNotFoundError:
        store.publish(course.location, author.id)
        published_course, published_blocks, olx = _published_fixture(fixture)
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
    update_course_structure.apply(args=[text_type(course_key)])
    update_course_in_cache(course_key)
    return published_course, published_blocks, olx


def _ensure_site(fixture):
    Site.objects.filter(domain=fixture['site_domain']).exclude(pk=settings.SITE_ID).delete()
    site, _created = Site.objects.update_or_create(
        pk=settings.SITE_ID,
        defaults={
            'domain': fixture['site_domain'],
            'name': 'P1-B ORA2 {}'.format(fixture['runtime']),
        },
    )
    config, _created = SiteConfiguration.objects.get_or_create(
        site=site,
        defaults={'enabled': True, 'values': {}},
    )
    values = dict(config.values or {})
    values.update({'course_org_filter': fixture['course_key_object'].org, 'ENABLE_LAST_ACTIVITY': True})
    config.enabled = True
    config.values = values
    config.save()
    if site.pk != settings.SITE_ID or config.get_value('course_org_filter') != fixture['course_key_object'].org:
        raise RuntimeError('current Site is not bound to the gate course organization')
    return site


def _ensure_forums_disabled():
    config = ForumsConfig.current()
    config.enabled = False
    config.save()
    if config.enabled:
        raise RuntimeError('ForumsConfig must be disabled for the ORA2 gate')
    return config


def _ensure_completion_switch():
    switch_name = '{}.{}'.format(
        completion_waffle.WAFFLE_NAMESPACE,
        completion_waffle.ENABLE_COMPLETION_TRACKING,
    )
    switch, _created = Switch.objects.get_or_create(name=switch_name, defaults={'active': True})
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
    expected = {
        'global_enabled': True,
        'enabled_for_all_courses': False,
        'course_enabled': True,
        'effective': True,
    }
    if state != expected:
        raise RuntimeError('persistent grades configuration is invalid: {!r}'.format(state))
    return state


def _ensure_persistent_grades(fixture):
    PersistentGradesEnabledFlag.objects.create(enabled=True, enabled_for_all_courses=False)
    CoursePersistentGradesFlag.objects.create(course_id=fixture['course_key_object'], enabled=True)
    return _persistent_grades_state(fixture)


def _ensure_personas(fixture, learner, staff):
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
    CourseAccessRole.objects.filter(user=learner).delete()
    CourseAccessRole.objects.filter(user=staff).delete()
    CourseStaffRole(course_key).add_users(staff)
    if not CourseEnrollment.is_enrolled(learner, course_key):
        raise RuntimeError('ORA2 learner is not actively enrolled')
    return enrollment


def _student_item(fixture, learner):
    return StudentItem.objects.filter(
        student_id=anonymous_id_for_user(learner, fixture['course_key_object']),
        course_id=text_type(fixture['course_key_object']),
        item_id=text_type(fixture['usage_keys']['openassessment']),
        item_type='openassessment',
    ).first()


def _submission_rows(student_item):
    if student_item is None:
        return Submission._objects.none()
    return Submission._objects.filter(student_item=student_item)


def _model_snapshot(fixture, learner, staff):
    course_key = fixture['course_key_object']
    ora2_key = fixture['usage_keys']['openassessment']
    subsection_key = fixture['usage_keys']['sequential']
    learner_anonymous_id = anonymous_id_for_user(learner, course_key)
    staff_anonymous_id = anonymous_id_for_user(staff, course_key)
    student_item = _student_item(fixture, learner)
    submissions = _submission_rows(student_item)
    submission_uuids = [text_type(value) for value in submissions.values_list('uuid', flat=True)]
    scores = Score.objects.filter(student_item=student_item) if student_item is not None else Score.objects.none()
    assessments = Assessment.objects.filter(submission_uuid__in=submission_uuids)
    rubric_ids = list(assessments.values_list('rubric_id', flat=True))
    workflows = AssessmentWorkflow.objects.filter(
        course_id=text_type(course_key), item_id=text_type(ora2_key), submission_uuid__in=submission_uuids,
    )
    staff_workflows = StaffWorkflow.objects.filter(
        course_id=text_type(course_key), item_id=text_type(ora2_key), submission_uuid__in=submission_uuids,
    )
    enrollment = CourseEnrollment.objects.filter(user=learner, course_id=course_key).first()
    student_module = StudentModule.objects.filter(
        student=learner, course_id=course_key, module_state_key=ora2_key,
    ).first()
    subsection_grade = PersistentSubsectionGrade.objects.filter(
        user_id=learner.id, course_id=course_key, usage_key=subsection_key,
    ).first()
    course_grade = PersistentCourseGrade.objects.filter(user_id=learner.id, course_id=course_key).first()
    course_progress = PersistentCourseProgress.objects.filter(user_id=learner.id, course_id=course_key).first()
    completion = BlockCompletion.objects.filter(user=learner, course_key=course_key, block_key=ora2_key).first()
    current_score = None
    if student_item is not None:
        summary = ScoreSummary.objects.filter(student_item=student_item).select_related('latest', 'highest').first()
        if summary is not None:
            current_score = summary.latest
    return {
        'learner_anonymous_id': learner_anonymous_id,
        'staff_anonymous_id': staff_anonymous_id,
        'student_item_object': student_item,
        'submission_objects': list(submissions.order_by('id')),
        'score_objects': list(scores.order_by('id')),
        'current_score_object': current_score,
        'assessment_objects': list(assessments.order_by('id')),
        'workflow_objects': list(workflows.order_by('id')),
        'staff_workflow_objects': list(staff_workflows.order_by('id')),
        'student_module_object': student_module,
        'subsection_grade_object': subsection_grade,
        'course_grade_object': course_grade,
        'course_progress_object': course_progress,
        'completion_object': completion,
        'enrollment_object': enrollment,
        'counts': {
            'student_item': 1 if student_item is not None else 0,
            'submission_active': submissions.filter(status=Submission.ACTIVE).count(),
            'submission_total': submissions.count(),
            'score_total': scores.count(),
            'score_reset': scores.filter(reset=True).count(),
            'score_current_non_reset': 1 if current_score is not None and not current_score.reset else 0,
            'score_annotation': ScoreAnnotation.objects.filter(score__in=scores).count(),
            'assessment': assessments.count(),
            'assessment_part': AssessmentPart.objects.filter(assessment__in=assessments).count(),
            'rubric': Rubric.objects.filter(id__in=rubric_ids).count(),
            'criterion': Criterion.objects.filter(rubric_id__in=rubric_ids).count(),
            'criterion_option': CriterionOption.objects.filter(criterion__rubric_id__in=rubric_ids).count(),
            'assessment_workflow': workflows.count(),
            'assessment_workflow_step': AssessmentWorkflowStep.objects.filter(workflow__in=workflows).count(),
            'assessment_workflow_cancellation': AssessmentWorkflowCancellation.objects.filter(
                workflow__in=workflows
            ).count(),
            'staff_workflow': staff_workflows.count(),
            'student_module': 1 if student_module is not None else 0,
            'block_completion': 1 if completion is not None else 0,
            'subsection_grade': 1 if subsection_grade is not None else 0,
            'course_grade': 1 if course_grade is not None else 0,
            'course_progress': 1 if course_progress is not None else 0,
            'subsection_override': PersistentSubsectionGradeOverride.objects.filter(
                grade__user_id=learner.id, grade__course_id=course_key,
            ).count(),
            'certificate': GeneratedCertificate.objects.filter(user=learner, course_id=course_key).count(),
        },
    }


def _public_snapshot(state):
    result = dict(state['counts'])
    result.update({
        'learner_anonymous_id': state['learner_anonymous_id'],
        'staff_anonymous_id': state['staff_anonymous_id'],
    })
    enrollment = state['enrollment_object']
    result['enrollment'] = 1 if enrollment is not None and enrollment.is_active else 0
    result['enrollment_mode'] = enrollment.mode if enrollment is not None else None
    result['enrollment_completion_date'] = (
        text_type(enrollment.completion_date)
        if enrollment is not None and enrollment.completion_date is not None else None
    )
    return result


def _assert_zero_precondition(state):
    nonzero = {name: value for name, value in state['counts'].items() if value != 0}
    if nonzero:
        raise RuntimeError('gate-owned ORA2 precondition rows remain: {!r}'.format(nonzero))
    enrollment = state['enrollment_object']
    if (
            enrollment is None or not enrollment.is_active or
            enrollment.mode != CourseMode.AUDIT or enrollment.completion_date is not None
    ):
        raise RuntimeError('active audit enrollment precondition is invalid')


def _prepare_queues():
    from kombu import Connection

    queues = getattr(settings, 'ORA2_GATE_QUEUES', {})
    exchange_name = settings.CELERY_DEFAULT_EXCHANGE
    purged = {}
    connection = Connection(settings.BROKER_URL, connect_timeout=3)
    with connection as conn:
        channel = conn.channel()
        channel.exchange_declare(exchange=exchange_name, type='direct', durable=True, auto_delete=False)
        for role, queue in queues.items():
            channel.queue_declare(queue=queue, durable=True, auto_delete=False)
            channel.queue_bind(queue=queue, exchange=exchange_name, routing_key=queue)
            purged[role] = channel.queue_purge(queue=queue)
        channel.close()
    return purged


def _queue_snapshot():
    from kombu import Connection

    result = {}
    try:
        connection = Connection(settings.BROKER_URL, connect_timeout=3)
        with connection as conn:
            channel = conn.channel()
            for role, queue in settings.ORA2_GATE_QUEUES.items():
                declared = channel.queue_declare(queue=queue, passive=True)
                result[role] = {
                    'queue': queue,
                    'messages_ready': declared.message_count,
                    'consumers': declared.consumer_count,
                }
            channel.close()
    except Exception as exc:
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
    except Exception as exc:
        return {'error': _redact(text_type(exc))}


def _assert_idle(queue_state, worker_state):
    if queue_state.get('broker_error'):
        raise RuntimeError('queue snapshot failed: {!r}'.format(queue_state))
    for role, item in queue_state.items():
        if item.get('messages_ready') != 0:
            raise RuntimeError('ORA2 queue is not idle for {}: {!r}'.format(role, item))
        expected_consumers = 1 if role in ('grade', 'progress') else 0
        if item.get('consumers') != expected_consumers:
            raise RuntimeError('ORA2 queue consumer count is invalid for {}: {!r}'.format(role, item))
    if worker_state.get('error') or len(worker_state.get('ping', [])) != 1:
        raise RuntimeError('ORA2 worker ping is invalid: {!r}'.format(worker_state))
    if not all(worker_state.get('registered_required', {}).values()):
        raise RuntimeError('ORA2 downstream tasks are not registered: {!r}'.format(worker_state))
    for state_name in ('active', 'reserved', 'scheduled'):
        if any(tasks for tasks in worker_state.get(state_name, {}).values()):
            raise RuntimeError('ORA2 worker is not idle in {}: {!r}'.format(
                state_name, worker_state.get(state_name)
            ))


def _offset_path(fixture, log_kind):
    return os.path.join(
        fixture['handshake_dir'],
        'attempt{}-{}.offset'.format(fixture['attempt'], log_kind),
    )


def _record_log_offsets(fixture):
    if not os.path.isdir(fixture['handshake_dir']):
        os.makedirs(fixture['handshake_dir'])
    recorded = {}
    for log_kind, log_path in (('worker', fixture['worker_log']), ('lms', fixture['lms_log'])):
        offset_path = _offset_path(fixture, log_kind)
        if os.path.exists(offset_path):
            raise RuntimeError('refusing prior attempt handshake: {}'.format(offset_path))
        offset = os.path.getsize(log_path) if os.path.exists(log_path) else 0
        with open(offset_path, 'w') as offset_file:
            offset_file.write(text_type(offset))
        recorded[log_kind] = {'path': log_path, 'offset': offset, 'offset_file': offset_path}
    return recorded


def _read_log_window(fixture, log_kind):
    log_path = fixture['worker_log'] if log_kind == 'worker' else fixture['lms_log']
    offset_path = _offset_path(fixture, log_kind)
    with open(offset_path, 'r') as offset_file:
        offset = int(offset_file.read().strip())
    with open(log_path, 'r') as log_file:
        log_file.seek(offset)
        return log_file.read()


def _task_log_summary(fixture):
    content = _read_log_window(fixture, 'worker')
    names = {
        'grade': 'lms.djangoapps.grades.tasks.recalculate_subsection_grade_v3',
        'progress': 'lms.djangoapps.grades.tasks.calculate_course_progress',
    }
    summary = {'path': fixture['worker_log'], 'window_bytes': len(content)}
    for role, task_name in names.items():
        pattern = re.escape(task_name)
        received = re.findall(
            r'^([^\n]*?)Received task: %s\[([^\]]+)\]' % pattern,
            content,
            re.MULTILINE,
        )
        succeeded = re.findall(
            r'^([^\n]*?)Task %s\[([^\]]+)\] succeeded' % pattern,
            content,
            re.MULTILINE,
        )
        retry = re.findall(
            r'^([^\n]*?)%s\[([^\]]+)\].*(?:retry|Retry)' % pattern,
            content,
            re.MULTILINE,
        )
        summary[role] = {
            'task_name': task_name,
            'received_records': len(received),
            'successes': len(succeeded),
            'retry_records': len(retry),
            'received': [{'prefix': prefix.strip(), 'task_id': task_id} for prefix, task_id in received],
            'succeeded': [{'prefix': prefix.strip(), 'task_id': task_id} for prefix, task_id in succeeded],
            'task_ids': sorted(set(task_id for _prefix, task_id in received + succeeded)),
        }
    return summary


def _assert_task_summary(summary):
    for role in ('grade', 'progress'):
        item = summary[role]
        received_ids = [record['task_id'] for record in item['received']]
        succeeded_ids = [record['task_id'] for record in item['succeeded']]
        if (
                item['received_records'] != 1 or item['successes'] != 1 or
                item['retry_records'] != 0 or len(set(received_ids)) != 1 or
                set(received_ids) != set(succeeded_ids)
        ):
            raise RuntimeError('ORA2 {} task cardinality is invalid: {!r}'.format(role, item))


def _assert_no_task_summary(summary):
    for role in ('grade', 'progress'):
        item = summary[role]
        if (
                item['received_records'] != 0 or item['successes'] != 0 or
                item['retry_records'] != 0 or item['task_ids']
        ):
            raise RuntimeError('ORA2 {} task ran before staff assessment: {!r}'.format(role, item))


def _source_identity():
    import openassessment
    from openassessment.xblock.openassessmentblock import OpenAssessmentBlock

    ora2_distribution = pkg_resources.get_distribution('ora2')
    submissions_distribution = pkg_resources.get_distribution('edx-submissions')
    package_root = os.path.dirname(openassessment.__file__)
    direct_url_path = os.path.join(ora2_distribution.egg_info, 'direct_url.json')
    direct_url = None
    if os.path.isfile(direct_url_path):
        with open(direct_url_path, 'r') as direct_url_file:
            direct_url = json.load(direct_url_file)
    git_commit = None
    search_root = package_root
    while search_root and search_root != os.path.dirname(search_root):
        if os.path.isdir(os.path.join(search_root, '.git')):
            git_commit = subprocess.check_output(
                ['git', '-C', search_root, 'rev-parse', 'HEAD']
            ).decode('ascii').strip()
            break
        search_root = os.path.dirname(search_root)
    direct_commit = None
    if direct_url:
        direct_commit = direct_url.get('vcs_info', {}).get('commit_id')
    resolved_commit = direct_commit or git_commit
    if resolved_commit != EXPECTED_ORA2_COMMIT:
        raise RuntimeError('installed ORA2 source identity is invalid: {!r}'.format({
            'direct_commit': direct_commit,
            'git_commit': git_commit,
            'package_root': package_root,
        }))
    fixture = _fixture()
    if submissions_distribution.version != fixture['submissions_version']:
        raise RuntimeError('installed edx-submissions version is invalid: {}'.format(
            submissions_distribution.version
        ))
    entry_points = list(pkg_resources.iter_entry_points('xblock.v1', 'openassessment'))
    if len(entry_points) != 1 or entry_points[0].load() is not OpenAssessmentBlock:
        raise RuntimeError('openassessment XBlock entry point is not exact: {!r}'.format(entry_points))
    required_statuses = ['staff', 'peer', 'self', 'training', 'waiting', 'done', 'cancelled']
    if not isinstance(AssessmentWorkflow.STEPS, list):
        raise RuntimeError('AssessmentWorkflow.STEPS is not a concrete list')
    if not all(value in AssessmentWorkflow.STATUS_VALUES for value in required_statuses):
        raise RuntimeError('AssessmentWorkflow status values are incomplete: {!r}'.format(
            AssessmentWorkflow.STATUS_VALUES
        ))
    if StaffAssessmentMixin is None or StaffAreaMixin is None:
        raise RuntimeError('ORA2 staff XBlock mixins did not import')
    resource_hashes = {}
    for relative_path in (
            'xblock/static/css/openassessment.css',
            'xblock/static/css/openassessment-ltr.css',
            'xblock/static/js/openassessment-lms.min.js'):
        full_path = os.path.join(package_root, relative_path)
        with open(full_path, 'rb') as resource_file:
            resource_hashes[relative_path] = hashlib.sha256(resource_file.read()).hexdigest()
    return {
        'ora2_distribution_version': ora2_distribution.version,
        'ora2_package_root': package_root,
        'ora2_direct_url': direct_url,
        'ora2_git_commit': git_commit,
        'ora2_resolved_commit': resolved_commit,
        'submissions_version': submissions_distribution.version,
        'entry_point': '{}.{}'.format(OpenAssessmentBlock.__module__, OpenAssessmentBlock.__name__),
        'workflow_steps': AssessmentWorkflow.STEPS,
        'workflow_status_values': AssessmentWorkflow.STATUS_VALUES,
        'resource_hashes': resource_hashes,
    }


def _platform_identity():
    source_root = settings.REPO_ROOT
    commit = subprocess.check_output(['git', '-C', source_root, 'rev-parse', 'HEAD']).decode('ascii').strip()
    tree = subprocess.check_output(['git', '-C', source_root, 'rev-parse', 'HEAD^{tree}']).decode('ascii').strip()
    if commit != EXPECTED_PLATFORM_COMMIT or tree != EXPECTED_PLATFORM_TREE:
        raise RuntimeError('mounted Platform identity is invalid: {} {}'.format(commit, tree))
    return {'source_root': source_root, 'commit': commit, 'tree': tree}


def identity(fixture):
    _emit('IDENTITY_OK', {
        'runtime': fixture['runtime'],
        'namespace': fixture['namespace'],
        'platform': _platform_identity(),
        'packages': _source_identity(),
        'settings': {
            'celery_always_eager': settings.CELERY_ALWAYS_EAGER,
            'celery_task_always_eager': settings.CELERY_TASK_ALWAYS_EAGER,
            'ora2_assessments': settings.ORA2_ASSESSMENTS,
            'ora2_score_priority': settings.ORA2_ASSESSMENT_SCORE_PRIORITY,
            'ora2_fileupload_backend': settings.ORA2_FILEUPLOAD_BACKEND,
            'grade_routing_key': settings.RECALCULATE_GRADES_ROUTING_KEY,
            'progress_routing_key': settings.RECALCULATE_PROGRESS_ROUTING_KEY,
        },
    })


def provision(fixture):
    author = _get_or_create_user(fixture['author'], fixture['author_email'], privileged=True)
    learner = _get_or_create_user(fixture['username'], fixture['email'], privileged=False)
    staff = _get_or_create_user(fixture['staff_username'], fixture['staff_email'], privileged=False)
    persistent_grades = _ensure_persistent_grades(fixture)
    course, blocks, olx = _ensure_course(fixture, author)
    purged_queues = _prepare_queues()
    site = _ensure_site(fixture)
    forums_config = _ensure_forums_disabled()
    switch_name = _ensure_completion_switch()
    enrollment = _ensure_personas(fixture, learner, staff)
    state = _model_snapshot(fixture, learner, staff)
    _assert_zero_precondition(state)
    _emit('PROVISION_OK', {
        'runtime': fixture['runtime'],
        'namespace': fixture['namespace'],
        'course_key': text_type(fixture['course_key_object']),
        'published_usage_keys': [text_type(block.location) for block in blocks],
        'ora2_olx_sha256': hashlib.sha256(olx.encode('utf8')).hexdigest(),
        'course_status': course.course_status,
        'grading_policy': course.grading_policy,
        'persistent_grades': persistent_grades,
        'completion_switch': switch_name,
        'forums_enabled': forums_config.enabled,
        'learner': {'username': learner.username, 'id': learner.id, 'is_staff': learner.is_staff},
        'staff': {'username': staff.username, 'id': staff.id, 'is_staff': staff.is_staff},
        'enrollment': {
            'active': enrollment.is_active,
            'mode': enrollment.mode,
            'origin': enrollment.origin,
            'completion_date': enrollment.completion_date,
        },
        'site': {'id': site.id, 'domain': site.domain},
        'row_counts': _public_snapshot(state),
        'purged_setup_queues': purged_queues,
    })


def _persona_assertions(fixture, learner, staff):
    if learner.is_staff or learner.is_superuser or not learner.is_active:
        raise RuntimeError('ORA2 learner privilege/active state is invalid')
    if staff.is_staff or staff.is_superuser or not staff.is_active:
        raise RuntimeError('ORA2 course staff global privilege/active state is invalid')
    learner_roles = list(CourseAccessRole.objects.filter(user=learner).values('role', 'org', 'course_id'))
    staff_roles = list(CourseAccessRole.objects.filter(user=staff).values('role', 'org', 'course_id'))
    expected_staff_roles = [{
        'role': 'staff',
        'org': fixture['course_key_object'].org,
        'course_id': fixture['course_key_object'],
    }]
    if learner_roles or staff_roles != expected_staff_roles:
        raise RuntimeError('ORA2 persona course roles are invalid: learner={!r} staff={!r}'.format(
            learner_roles, staff_roles
        ))
    return {'learner_roles': learner_roles, 'staff_roles': staff_roles}


def preflight(fixture):
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    staff = User.objects.get(username=fixture['staff_username'], email=fixture['staff_email'])
    roles = _persona_assertions(fixture, learner, staff)
    course, blocks, olx = _published_fixture(fixture)
    overview = CourseOverview.load_from_module_store(fixture['course_key_object'])
    if overview.course_status != COURSE_RELEASED_STATUS:
        raise RuntimeError('ORA2 course overview is not released')
    if ForumsConfig.current().enabled:
        raise RuntimeError('ForumsConfig must be disabled for the ORA2 gate')
    _ensure_completion_switch()
    persistent_grades = _persistent_grades_state(fixture)
    state = _model_snapshot(fixture, learner, staff)
    _assert_zero_precondition(state)
    queue_state = _queue_snapshot()
    worker_state = _worker_snapshot()
    _assert_idle(queue_state, worker_state)
    offsets = _record_log_offsets(fixture)
    _emit('PRECONDITION_OK', {
        'runtime': fixture['runtime'],
        'attempt': fixture['attempt'],
        'namespace': fixture['namespace'],
        'course_key': text_type(fixture['course_key_object']),
        'published_usage_keys': [text_type(block.location) for block in blocks],
        'ora2_usage_key': text_type(fixture['usage_keys']['openassessment']),
        'subsection_key': text_type(fixture['usage_keys']['sequential']),
        'ora2_olx': olx,
        'ora2_olx_sha256': hashlib.sha256(olx.encode('utf8')).hexdigest(),
        'course_status': course.course_status,
        'grading_policy': course.grading_policy,
        'grading_policy_hash': GradesTransformer.grading_policy_hash(course),
        'persistent_grades': persistent_grades,
        'personas': roles,
        'row_counts': _public_snapshot(state),
        'queue_state': queue_state,
        'worker_state': worker_state,
        'log_offsets': offsets,
        'broker': {
            'host': settings.RABBIT_CONTAINER,
            'port': 5672,
            'vhost': settings.RABBIT_VHOST,
            'user': settings.RABBIT_USER,
            'password_configured': bool(settings.RABBIT_PASSWORD),
            'queues': settings.ORA2_GATE_QUEUES,
        },
        'cache': settings.CACHES.get('default'),
        'sql': {key: value.get('NAME') for key, value in settings.DATABASES.items()},
        'mongo': {
            'module_store': settings.MODULESTORE['default']['OPTIONS']['stores'][0]['DOC_STORE_CONFIG'].get('db'),
            'content_store': settings.CONTENTSTORE.get('DOC_STORE_CONFIG', {}).get('db'),
        },
        'celery_always_eager': settings.CELERY_ALWAYS_EAGER,
    })


def _single_submission_state(fixture, learner, staff):
    state = _model_snapshot(fixture, learner, staff)
    submissions = state['submission_objects']
    if len(submissions) != 1:
        raise RuntimeError('expected exactly one ORA2 submission: {!r}'.format(state['counts']))
    submission = submissions[0]
    answer = submission.answer
    parts = answer.get('parts', []) if isinstance(answer, dict) else []
    if (
            submission.status != Submission.ACTIVE or submission.attempt_number != 1 or
            len(parts) != 1 or parts[0].get('text') != fixture['response_marker']
    ):
        raise RuntimeError('ORA2 submission content/attempt is invalid: {!r}'.format({
            'status': submission.status,
            'attempt': submission.attempt_number,
            'answer': answer,
        }))
    return state, submission


def _pending_persistent_state(fixture, state, submission):
    subsection_grade = state['subsection_grade_object']
    course_grade = state['course_grade_object']
    progress = state['course_progress_object']
    course, _blocks, _olx = _published_fixture(fixture)
    policy_hash = GradesTransformer.grading_policy_hash(course)
    if (
            subsection_grade is None or course_grade is None or progress is None or
            subsection_grade.user_id != state['enrollment_object'].user_id or
            subsection_grade.course_id != fixture['course_key_object'] or
            subsection_grade.usage_key != fixture['usage_keys']['sequential'] or
            float(subsection_grade.earned_all) != 0.0 or float(subsection_grade.possible_all) != 1.0 or
            float(subsection_grade.earned_graded) != 0.0 or float(subsection_grade.possible_graded) != 1.0 or
            subsection_grade.first_attempted is not None or
            float(course_grade.percent_grade) != 0.0 or course_grade.letter_grade != '' or
            course_grade.grading_policy_hash != policy_hash or
            float(progress.percent_progress) != 0.0 or
            any(value.created > submission.submitted_at for value in (subsection_grade, course_grade, progress))
    ):
        raise RuntimeError('ORA2 pending persistent grade/progress state is invalid')
    return {
        'subsection_grade': {
            'id': subsection_grade.id,
            'earned_all': subsection_grade.earned_all,
            'possible_all': subsection_grade.possible_all,
            'earned_graded': subsection_grade.earned_graded,
            'possible_graded': subsection_grade.possible_graded,
            'first_attempted': subsection_grade.first_attempted,
            'created': subsection_grade.created,
        },
        'course_grade': {
            'id': course_grade.id,
            'percent_grade': course_grade.percent_grade,
            'letter_grade': course_grade.letter_grade,
            'grading_policy_hash': course_grade.grading_policy_hash,
            'created': course_grade.created,
        },
        'course_progress': {
            'id': progress.id,
            'percent_progress': progress.percent_progress,
            'created': progress.created,
        },
    }


def submission_ready(fixture):
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    staff = User.objects.get(username=fixture['staff_username'], email=fixture['staff_email'])
    state, submission = _single_submission_state(fixture, learner, staff)
    counts = state['counts']
    expected = {
        'student_item': 1,
        'submission_active': 1,
        'submission_total': 1,
        'assessment_workflow': 1,
        'assessment_workflow_step': 1,
        'staff_workflow': 1,
        'student_module': 1,
        'subsection_grade': 1,
        'course_grade': 1,
        'course_progress': 1,
    }
    mismatched = {name: (counts[name], value) for name, value in expected.items() if counts[name] != value}
    forbidden = (
        'score_total', 'score_annotation', 'assessment', 'assessment_part', 'rubric', 'criterion',
        'criterion_option', 'assessment_workflow_cancellation', 'block_completion', 'subsection_override',
        'certificate',
    )
    mismatched.update({name: (counts[name], 0) for name in forbidden if counts[name] != 0})
    if mismatched:
        raise RuntimeError('ORA2 submission-ready row cardinality is invalid: {!r}'.format(mismatched))
    workflow = state['workflow_objects'][0]
    step = workflow.steps.get()
    staff_workflow = state['staff_workflow_objects'][0]
    student_module = state['student_module_object']
    module_state = json.loads(student_module.state or '{}')
    if (
            workflow.status != 'waiting' or workflow.is_cancelled or workflow.submission_uuid != text_type(submission.uuid) or
            step.name != 'staff' or step.submitter_completed_at is None or step.assessment_completed_at is not None or
            staff_workflow.scorer_id != '' or staff_workflow.grading_started_at is not None or
            staff_workflow.grading_completed_at is not None or staff_workflow.cancelled_at is not None or
            text_type(module_state.get('submission_uuid')) != text_type(submission.uuid) or
            student_module.grade is not None or student_module.max_grade is not None
    ):
        raise RuntimeError('ORA2 submission-ready workflow/state is invalid')
    queue_state = _queue_snapshot()
    worker_state = _worker_snapshot()
    _assert_idle(queue_state, worker_state)
    pending_persistent_state = _pending_persistent_state(fixture, state, submission)
    task_summary = _task_log_summary(fixture)
    _assert_no_task_summary(task_summary)
    _emit('SUBMISSION_READY_OK', {
        'runtime': fixture['runtime'],
        'attempt': fixture['attempt'],
        'response_marker': fixture['response_marker'],
        'submission': {
            'uuid': text_type(submission.uuid),
            'attempt_number': submission.attempt_number,
            'submitted_at': submission.submitted_at,
            'created_at': submission.created_at,
            'answer': submission.answer,
        },
        'workflow': {
            'id': workflow.id,
            'status': workflow.status,
            'step': step.name,
            'submitter_completed_at': step.submitter_completed_at,
            'assessment_completed_at': step.assessment_completed_at,
        },
        'staff_workflow': {
            'id': staff_workflow.id,
            'scorer_id': staff_workflow.scorer_id,
            'grading_started_at': staff_workflow.grading_started_at,
            'grading_completed_at': staff_workflow.grading_completed_at,
        },
        'xblock_state': module_state,
        'pending_persistent_state': pending_persistent_state,
        'row_counts': _public_snapshot(state),
        'task_summary': task_summary,
        'queue_state': queue_state,
        'worker_state': worker_state,
    })


def staff_lease(fixture):
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    staff = User.objects.get(username=fixture['staff_username'], email=fixture['staff_email'])
    state, submission = _single_submission_state(fixture, learner, staff)
    counts = state['counts']
    if any(counts[name] for name in (
            'score_total', 'score_annotation', 'assessment', 'assessment_part', 'rubric', 'criterion',
            'criterion_option', 'block_completion', 'subsection_override', 'certificate',
    )):
        raise RuntimeError('ORA2 staff lease has premature assessment/score/task side effects: {!r}'.format(counts))
    workflow = state['workflow_objects'][0]
    staff_workflow = state['staff_workflow_objects'][0]
    if (
            workflow.status != 'waiting' or
            staff_workflow.submission_uuid != text_type(submission.uuid) or
            staff_workflow.scorer_id != state['staff_anonymous_id'] or
            staff_workflow.grading_started_at is None or
            staff_workflow.grading_completed_at is not None or
            staff_workflow.cancelled_at is not None
    ):
        raise RuntimeError('ORA2 staff lease is not assigned exactly to course staff')
    statistics = StaffWorkflow.get_workflow_statistics(
        text_type(fixture['course_key_object']), text_type(fixture['usage_keys']['openassessment'])
    )
    if statistics != {'graded': 0, 'ungraded': 0, 'in-progress': 1}:
        raise RuntimeError('ORA2 staff lease statistics are invalid: {!r}'.format(statistics))
    queue_state = _queue_snapshot()
    worker_state = _worker_snapshot()
    _assert_idle(queue_state, worker_state)
    pending_persistent_state = _pending_persistent_state(fixture, state, submission)
    task_summary = _task_log_summary(fixture)
    _assert_no_task_summary(task_summary)
    _emit('STAFF_LEASE_OK', {
        'runtime': fixture['runtime'],
        'attempt': fixture['attempt'],
        'submission_uuid': text_type(submission.uuid),
        'response_marker': fixture['response_marker'],
        'staff_anonymous_id': state['staff_anonymous_id'],
        'staff_workflow': {
            'id': staff_workflow.id,
            'scorer_id': staff_workflow.scorer_id,
            'grading_started_at': staff_workflow.grading_started_at,
            'grading_completed_at': staff_workflow.grading_completed_at,
        },
        'statistics': statistics,
        'pending_persistent_state': pending_persistent_state,
        'row_counts': _public_snapshot(state),
        'task_summary': task_summary,
        'queue_state': queue_state,
        'worker_state': worker_state,
    })


def _postcondition_payload(fixture, learner, staff):
    state, submission = _single_submission_state(fixture, learner, staff)
    counts = state['counts']
    required_counts = {
        'student_item': 1,
        'submission_active': 1,
        'submission_total': 1,
        'score_total': 2,
        'score_reset': 1,
        'score_current_non_reset': 1,
        'score_annotation': 1,
        'assessment': 1,
        'assessment_part': 1,
        'rubric': 1,
        'criterion': 1,
        'criterion_option': 2,
        'assessment_workflow': 1,
        'assessment_workflow_step': 1,
        'assessment_workflow_cancellation': 0,
        'staff_workflow': 1,
        'student_module': 1,
        'block_completion': 1,
        'subsection_grade': 1,
        'course_grade': 1,
        'course_progress': 1,
        'subsection_override': 0,
        'certificate': 0,
    }
    mismatched = {name: (counts[name], value) for name, value in required_counts.items() if counts[name] != value}
    if mismatched:
        raise RuntimeError('ORA2 final row cardinality is invalid: {!r}'.format(mismatched))
    assessment = state['assessment_objects'][0]
    part = assessment.parts.select_related('criterion', 'option').get()
    workflow = state['workflow_objects'][0]
    step = workflow.steps.get()
    staff_workflow = state['staff_workflow_objects'][0]
    score = state['current_score_object']
    annotation = ScoreAnnotation.objects.get(score=score)
    student_module = state['student_module_object']
    module_state = json.loads(student_module.state or '{}')
    completion = state['completion_object']
    subsection_grade = state['subsection_grade_object']
    course_grade = state['course_grade_object']
    progress = state['course_progress_object']
    enrollment = state['enrollment_object']
    course, _blocks, _olx = _published_fixture(fixture)
    policy_hash = GradesTransformer.grading_policy_hash(course)
    if (
            assessment.submission_uuid != text_type(submission.uuid) or
            assessment.score_type != 'ST' or assessment.scorer_id != state['staff_anonymous_id'] or
            assessment.feedback != fixture['feedback_marker'] or
            assessment.points_earned != 2 or assessment.points_possible != 2 or
            part.criterion.name != 'response_quality' or part.option.name != 'meets_requirement' or
            part.points_earned != 2
    ):
        raise RuntimeError('ORA2 staff assessment/rubric result is invalid')
    if (
            workflow.status != 'done' or workflow.is_cancelled or
            step.name != 'staff' or step.submitter_completed_at is None or step.assessment_completed_at is None or
            staff_workflow.assessment != text_type(assessment.id) or
            staff_workflow.scorer_id != state['staff_anonymous_id'] or
            staff_workflow.grading_started_at is None or staff_workflow.grading_completed_at is None or
            staff_workflow.cancelled_at is not None
    ):
        raise RuntimeError('ORA2 final workflow is invalid')
    if (
            score is None or score.reset or score.submission_id != submission.id or
            score.points_earned != 2 or score.points_possible != 2 or
            annotation.annotation_type != 'staff_defined' or
            annotation.creator != state['staff_anonymous_id']
    ):
        raise RuntimeError('ORA2 submissions score/annotation is invalid')
    if (
            text_type(module_state.get('submission_uuid')) != text_type(submission.uuid) or
            student_module.grade is not None or student_module.max_grade is not None or
            float(completion.completion) != 1.0 or
            float(subsection_grade.earned_all) != 2.0 or float(subsection_grade.possible_all) != 2.0 or
            float(subsection_grade.earned_graded) != 2.0 or float(subsection_grade.possible_graded) != 2.0 or
            float(course_grade.percent_grade) != 1.0 or course_grade.letter_grade != 'Pass' or
            course_grade.grading_policy_hash != policy_hash or
            float(progress.percent_progress) != 1.0 or
            enrollment is None or not enrollment.is_active or enrollment.mode != CourseMode.AUDIT or
            enrollment.completion_date is None
    ):
        raise RuntimeError('ORA2 completion/persistent grade/progress state is invalid')
    statistics = StaffWorkflow.get_workflow_statistics(
        text_type(fixture['course_key_object']), text_type(fixture['usage_keys']['openassessment'])
    )
    if statistics != {'graded': 1, 'ungraded': 0, 'in-progress': 0}:
        raise RuntimeError('ORA2 final staff statistics are invalid: {!r}'.format(statistics))
    return state, {
        'submission': {
            'id': submission.id,
            'uuid': text_type(submission.uuid),
            'attempt_number': submission.attempt_number,
            'answer': submission.answer,
            'submitted_at': submission.submitted_at,
        },
        'assessment': {
            'id': assessment.id,
            'score_type': assessment.score_type,
            'scorer_id': assessment.scorer_id,
            'feedback': assessment.feedback,
            'scored_at': assessment.scored_at,
            'points_earned': assessment.points_earned,
            'points_possible': assessment.points_possible,
            'criterion': part.criterion.name,
            'option': part.option.name,
        },
        'workflow': {
            'id': workflow.id,
            'status': workflow.status,
            'step': step.name,
            'submitter_completed_at': step.submitter_completed_at,
            'assessment_completed_at': step.assessment_completed_at,
        },
        'staff_workflow': {
            'id': staff_workflow.id,
            'scorer_id': staff_workflow.scorer_id,
            'grading_started_at': staff_workflow.grading_started_at,
            'grading_completed_at': staff_workflow.grading_completed_at,
            'assessment_id': staff_workflow.assessment,
        },
        'score': {
            'id': score.id,
            'points_earned': score.points_earned,
            'points_possible': score.points_possible,
            'created_at': score.created_at,
            'annotation_type': annotation.annotation_type,
            'annotation_creator': annotation.creator,
            'annotation_reason': annotation.reason,
        },
        'xblock_state': module_state,
        'completion': {'id': completion.id, 'value': completion.completion, 'modified': completion.modified},
        'subsection_grade': {
            'id': subsection_grade.id,
            'earned_all': subsection_grade.earned_all,
            'possible_all': subsection_grade.possible_all,
            'earned_graded': subsection_grade.earned_graded,
            'possible_graded': subsection_grade.possible_graded,
            'modified': subsection_grade.modified,
        },
        'course_grade': {
            'id': course_grade.id,
            'percent_grade': course_grade.percent_grade,
            'letter_grade': course_grade.letter_grade,
            'grading_policy_hash': course_grade.grading_policy_hash,
            'modified': course_grade.modified,
        },
        'course_progress': {
            'id': progress.id,
            'percent_progress': progress.percent_progress,
            'modified': progress.modified,
        },
        'enrollment_completion_date': enrollment.completion_date,
        'statistics': statistics,
    }


def postflight(fixture):
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    staff = User.objects.get(username=fixture['staff_username'], email=fixture['staff_email'])
    deadline = time.time() + 90
    last_error = None
    while time.time() < deadline:
        try:
            state, payload = _postcondition_payload(fixture, learner, staff)
            queue_state = _queue_snapshot()
            worker_state = _worker_snapshot()
            _assert_idle(queue_state, worker_state)
            task_summary = _task_log_summary(fixture)
            _assert_task_summary(task_summary)
            lms_window = _read_log_window(fixture, 'lms')
            worker_window = _read_log_window(fixture, 'worker')
            forbidden_log_patterns = (
                'Traceback (most recent call last)',
                'Unable to load XBlock',
                'Task handler raised error',
                'CRITICAL',
            )
            log_findings = [
                pattern for pattern in forbidden_log_patterns
                if pattern in lms_window or pattern in worker_window
            ]
            if log_findings:
                raise RuntimeError('ORA2 business-window log findings: {!r}'.format(log_findings))
            payload.update({
                'runtime': fixture['runtime'],
                'attempt': fixture['attempt'],
                'response_marker': fixture['response_marker'],
                'feedback_marker': fixture['feedback_marker'],
                'row_counts': _public_snapshot(state),
                'task_summary': task_summary,
                'queue_state': queue_state,
                'worker_state': worker_state,
                'business_log_findings': log_findings,
            })
            _emit('POSTCONDITION_OK', payload)
            return
        except RuntimeError as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError('ORA2 postcondition did not settle: {}'.format(last_error))


def reset(fixture):
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    staff = User.objects.get(username=fixture['staff_username'], email=fixture['staff_email'])
    state, _payload = _postcondition_payload(fixture, learner, staff)
    course_key = fixture['course_key_object']
    ora2_key = fixture['usage_keys']['openassessment']
    subsection_key = fixture['usage_keys']['sequential']
    submissions = state['submission_objects']
    submission_uuids = [text_type(row.uuid) for row in submissions]
    assessments = Assessment.objects.filter(submission_uuid__in=submission_uuids)
    rubric_ids = list(assessments.values_list('rubric_id', flat=True))
    workflows = AssessmentWorkflow.objects.filter(submission_uuid__in=submission_uuids)
    AssessmentWorkflowCancellation.objects.filter(workflow__in=workflows).delete()
    AssessmentWorkflowStep.objects.filter(workflow__in=workflows).delete()
    workflows.delete()
    StaffWorkflow.objects.filter(submission_uuid__in=submission_uuids).delete()
    AssessmentPart.objects.filter(assessment__in=assessments).delete()
    assessments.delete()
    CriterionOption.objects.filter(criterion__rubric_id__in=rubric_ids).delete()
    Criterion.objects.filter(rubric_id__in=rubric_ids).delete()
    Rubric.objects.filter(id__in=rubric_ids).delete()
    student_item = state['student_item_object']
    scores = Score.objects.filter(student_item=student_item)
    ScoreAnnotation.objects.filter(score__in=scores).delete()
    ScoreSummary.objects.filter(student_item=student_item).delete()
    scores.delete()
    Submission._objects.filter(student_item=student_item).delete()
    student_item.delete()
    StudentModule.objects.filter(student=learner, course_id=course_key, module_state_key=ora2_key).delete()
    BlockCompletion.objects.filter(user=learner, course_key=course_key, block_key=ora2_key).delete()
    PersistentSubsectionGradeOverride.objects.filter(
        grade__user_id=learner.id, grade__course_id=course_key,
    ).delete()
    PersistentSubsectionGrade.objects.filter(
        user_id=learner.id, course_id=course_key, usage_key=subsection_key,
    ).delete()
    PersistentCourseGrade.objects.filter(user_id=learner.id, course_id=course_key).delete()
    PersistentCourseProgress.objects.filter(user_id=learner.id, course_id=course_key).delete()
    GeneratedCertificate.objects.filter(user=learner, course_id=course_key).delete()
    enrollment = CourseEnrollment.objects.get(user=learner, course_id=course_key)
    enrollment.completion_date = None
    enrollment.save(update_fields=['completion_date'])
    clear_course_from_cache(course_key)
    reset_state = _model_snapshot(fixture, learner, staff)
    _assert_zero_precondition(reset_state)
    queue_state = _queue_snapshot()
    worker_state = _worker_snapshot()
    _assert_idle(queue_state, worker_state)
    _emit('RESET_OK', {
        'runtime': fixture['runtime'],
        'attempt': fixture['attempt'],
        'namespace': fixture['namespace'],
        'preserved_course': True,
        'preserved_learner': True,
        'preserved_staff_role': True,
        'row_counts': _public_snapshot(reset_state),
        'queue_state': queue_state,
        'worker_state': worker_state,
    })


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            'usage: provision-p1b-ora2-assessment.py '
            '{identity|provision|preflight|submission-ready|staff-lease|postflight|reset}'
        )
    fixture = _fixture()
    actions = {
        'identity': identity,
        'provision': provision,
        'preflight': preflight,
        'submission-ready': submission_ready,
        'staff-lease': staff_lease,
        'postflight': postflight,
        'reset': reset,
    }
    action = sys.argv[1]
    if action not in actions:
        raise SystemExit('unknown ORA2 gate action: {}'.format(action))
    actions[action](fixture)


if __name__ == '__main__':
    main()
