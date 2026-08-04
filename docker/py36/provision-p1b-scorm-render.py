# -*- coding: utf-8 -*-
"""Provision and verify the disposable dual-runtime SCORM render fixture."""
from __future__ import absolute_import, division, print_function, unicode_literals

import hashlib
import json
import os
import pkg_resources
import subprocess
import sys
from datetime import datetime

import django
import pytz

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.contrib.sites.models import Site  # noqa: E402
from django.utils import timezone  # noqa: E402
from completion.models import BlockCompletion  # noqa: E402
from opaque_keys.edx.keys import CourseKey  # noqa: E402
from six import binary_type, text_type  # noqa: E402

from course_modes.models import CourseMode  # noqa: E402
from courseware.courses import get_course_with_access  # noqa: E402
from courseware.models import StudentModule  # noqa: E402
from lms.djangoapps.grades.models import PersistentCourseGrade, PersistentCourseProgress  # noqa: E402
from openedx.core.djangoapps.content.block_structure.api import clear_course_from_cache  # noqa: E402
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview  # noqa: E402
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration  # noqa: E402
from student.models import (  # noqa: E402
    CourseAccessRole,
    CourseEnrollment,
    EnrollmentOrigin,
    Registration,
    UserProfile,
)
from xmodule.course_module import COURSE_RELEASED_STATUS  # noqa: E402
from xmodule.modulestore import ModuleStoreEnum  # noqa: E402
from xmodule.modulestore.django import modulestore  # noqa: E402
from xmodule.modulestore.exceptions import DuplicateCourseError, ItemNotFoundError  # noqa: E402


SCORM_COMMIT = '8a6c07d562217500fa8236f555343c9921ef4907'
SCORM_TREE = '595e291da2d3a7983a290fdc433e1471805b2525'
SCORM_MODULE_SHA256 = '0b3b9304ecf20fb63009e8ba0b33857bbea3e868c25d9f087fb55d91438511b6'
SCORM_JS_SHA256 = '675ed5821f9d193ae46024e1d3d8d01efba0b1b37b254640460e97d5740bc772'
MARKER = 'P1B_SCORM_PACKAGE_RENDER_OK'
API_MARKER = 'P1B_SCORM_API_INIT'
DISPLAY_NAME = 'P1-B SCORM Render'
PACKAGE_ID = 'p1b-scorm-render-package'
PACKAGE_INDEX = PACKAGE_ID + '/index.html'
COURSE_START = datetime(2026, 8, 1, tzinfo=pytz.UTC)
COURSE_END = datetime(2027, 8, 1, tzinfo=pytz.UTC)
BLOCKS = (
    ('chapter', 'scorm_render_section', 'SCORM Render Section'),
    ('sequential', 'scorm_render_subsection', 'SCORM Render Subsection'),
    ('vertical', 'scorm_render_unit', 'SCORM Render Unit'),
    ('scormxblock', 'scorm_render_component', 'SCORM Render Component'),
)
RUNTIME_FIXTURES = {
    'py36': {
        'username': 'qascorm_py36',
        'email': 'qascorm_py36@example.com',
        'author': 'qascorm_author_py36',
        'author_email': 'qascorm_author_py36@example.com',
        'course_key': 'course-v1:QA+SCORMRender+Py36',
        'namespace': 'py36_r1_p1b_scorm_render_py36_r4',
        'site_domain': 'localhost:18147',
    },
    'py27': {
        'username': 'qascorm_py27',
        'email': 'qascorm_py27@example.com',
        'author': 'qascorm_author_py27',
        'author_email': 'qascorm_author_py27@example.com',
        'course_key': 'course-v1:QA+SCORMRender+Py27',
        'namespace': 'py36_r1_p1b_scorm_render_py27_r4',
        'site_domain': 'localhost:18148',
    },
}

PACKAGE_FILES = {
    'imsmanifest.xml': b'''<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="P1B_SCORM_RENDER" version="1.0"
 xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
 xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">
  <organizations default="P1B_ORG">
    <organization identifier="P1B_ORG">
      <title>P1-B SCORM Render</title>
      <item identifier="P1B_ITEM" identifierref="P1B_RESOURCE"><title>P1-B SCORM Render</title></item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="P1B_RESOURCE" type="webcontent" adlcp:scormtype="sco" href="index.html">
      <file href="index.html"/><file href="runtime.js"/><file href="package.css"/>
    </resource>
  </resources>
</manifest>
''',
    'index.html': b'''<!doctype html>
<html><head><meta charset="utf-8"><title>P1-B SCORM Render</title>
<link rel="stylesheet" href="package.css"></head>
<body><main><h1>P1-B SCORM Runtime</h1>
<p id="render-marker">P1B_SCORM_PACKAGE_RENDER_OK</p>
<p id="api-marker">P1B_SCORM_API_INIT=pending</p></main>
<script src="runtime.js"></script></body></html>
''',
    'runtime.js': b'''(function () {
    function initialize() {
        var api = window.parent && window.parent.API;
        var initialized = api && typeof api.LMSInitialize === 'function' ? api.LMSInitialize('') : 'missing';
        var text = 'P1B_SCORM_API_INIT=' + initialized;
        document.getElementById('api-marker').textContent = text;
        window.P1B_SCORM_STATE = {marker: 'P1B_SCORM_PACKAGE_RENDER_OK', initialized: initialized};
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }
}());
''',
    'package.css': b'''html,body{margin:0;padding:0;background:#fff;color:#17212b;font-family:Arial,sans-serif}main{padding:32px;border:6px solid #1f7a4d}h1{font-size:28px;margin:0 0 20px}p{font-size:18px;margin:10px 0}#render-marker{font-weight:bold;color:#12613c}''',
}
PACKAGE_HASHES = dict(
    (name, hashlib.sha256(content).hexdigest())
    for name, content in PACKAGE_FILES.items()
)


def _fixture():
    runtime = os.environ.get('PY36_R1_SCORM_RUNTIME')
    if runtime not in RUNTIME_FIXTURES:
        raise RuntimeError('PY36_R1_SCORM_RUNTIME must be py36 or py27')
    fixture = dict(RUNTIME_FIXTURES[runtime])
    fixture['runtime'] = runtime
    environment_values = {
        'username': 'PY36_R1_SCORM_USERNAME',
        'email': 'PY36_R1_SCORM_EMAIL',
        'course_key': 'PY36_R1_SCORM_COURSE_KEY',
        'namespace': 'PY36_R1_SCORM_NAMESPACE',
        'site_domain': 'PY36_R1_SCORM_SITE_DOMAIN',
    }
    for key, environment_name in environment_values.items():
        value = os.environ.get(environment_name, fixture[key])
        if value != fixture[key]:
            raise RuntimeError('{} must equal the gate-owned value {!r}'.format(environment_name, fixture[key]))
        fixture[key] = value
    fixture['course_key_object'] = CourseKey.from_string(fixture['course_key'])
    fixture['attempt'] = int(os.environ.get('PY36_R1_SCORM_ATTEMPT', '1'))
    if fixture['attempt'] not in (1, 2):
        raise RuntimeError('PY36_R1_SCORM_ATTEMPT must be 1 or 2')
    return fixture


def _text(value):
    if isinstance(value, binary_type):
        return value.decode('utf8')
    return text_type(value)


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as source_file:
        while True:
            chunk = source_file.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _scorm_source_identity(fixture):
    import scormxblock

    distribution = pkg_resources.get_distribution('scormxblock-xblock')
    module_root = os.path.dirname(os.path.realpath(scormxblock.__file__))
    module_file = os.path.join(module_root, 'scormxblock.py')
    js_file = os.path.join(module_root, 'static', 'js', 'src', 'scormxblock.js')
    if distribution.version != '0.2':
        raise RuntimeError('unexpected SCORM distribution version: {}'.format(distribution.version))
    if _sha256_file(module_file) != SCORM_MODULE_SHA256:
        raise RuntimeError('SCORM module hash mismatch: {}'.format(module_file))
    if _sha256_file(js_file) != SCORM_JS_SHA256:
        raise RuntimeError('SCORM JavaScript hash mismatch: {}'.format(js_file))

    if fixture['runtime'] == 'py36':
        direct_url_paths = list(distribution._get_metadata('direct_url.json'))
        if len(direct_url_paths) != 1:
            raise RuntimeError('SCORM direct_url metadata is missing')
        direct_url = json.loads(direct_url_paths[0])
        commit = direct_url.get('vcs_info', {}).get('commit_id')
    else:
        commit = _text(subprocess.check_output(['git', '-C', distribution.location, 'rev-parse', 'HEAD'])).strip()
        tree = _text(subprocess.check_output(['git', '-C', distribution.location, 'rev-parse', 'HEAD^{tree}'])).strip()
        if tree != SCORM_TREE:
            raise RuntimeError('SCORM source tree mismatch: {}'.format(tree))
    if commit != SCORM_COMMIT:
        raise RuntimeError('SCORM source commit mismatch: {}'.format(commit))

    entry_points = list(pkg_resources.iter_entry_points('xblock.v1', name='scormxblock'))
    if len(entry_points) != 1:
        raise RuntimeError('expected exactly one scormxblock entry point: {!r}'.format(entry_points))
    loaded_class = entry_points[0].load()
    if loaded_class.__name__ != 'ScormXBlock':
        raise RuntimeError('unexpected SCORM entry point class: {}'.format(loaded_class))
    return {
        'commit': commit,
        'tree': SCORM_TREE,
        'distribution': distribution.version,
        'module_file': module_file,
        'module_sha256': SCORM_MODULE_SHA256,
        'javascript_sha256': SCORM_JS_SHA256,
        'entry_point': text_type(entry_points[0]),
    }


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
                'p1b-scorm-{}'.format(username).encode('utf8')
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


def _write_package(block):
    package_fs = block.fs
    if package_fs.exists(PACKAGE_ID):
        package_fs.removetree(PACKAGE_ID)
    package_fs.makedirs(PACKAGE_ID, recreate=True)
    for filename, content in PACKAGE_FILES.items():
        with package_fs.open(PACKAGE_ID + '/' + filename, 'wb') as package_file:
            package_file.write(content)
    return _verify_package(block)


def _verify_package(block):
    package_fs = block.fs
    actual_hashes = {}
    for filename, expected_hash in PACKAGE_HASHES.items():
        package_path = PACKAGE_ID + '/' + filename
        if not package_fs.isfile(package_path):
            raise RuntimeError('SCORM package file is missing: {}'.format(package_path))
        with package_fs.open(package_path, 'rb') as package_file:
            actual_hash = hashlib.sha256(package_file.read()).hexdigest()
        if actual_hash != expected_hash:
            raise RuntimeError('SCORM package hash mismatch for {}: {}'.format(package_path, actual_hash))
        actual_hashes[filename] = actual_hash
    package_url = package_fs.get_url(PACKAGE_INDEX)
    if not package_url.endswith('/{}/index.html'.format(PACKAGE_ID)):
        raise RuntimeError('unexpected SCORM package URL: {}'.format(package_url))
    return {'url': package_url, 'hashes': actual_hashes}


def _published_fixture(store, fixture):
    course_key = fixture['course_key_object']
    usage_keys = [course_key.make_usage_key(block_type, block_id) for block_type, block_id, _ in BLOCKS]
    with store.branch_setting(ModuleStoreEnum.Branch.published_only, course_key):
        course = store.get_course(course_key)
        blocks = [store.get_item(usage_key) for usage_key in usage_keys]
    if course is None or course.course_status != COURSE_RELEASED_STATUS:
        raise RuntimeError('published released course is missing: {}'.format(course_key))
    scorm_block = blocks[-1]
    if scorm_block.scorm_pkg != PACKAGE_INDEX or scorm_block.display_name != BLOCKS[-1][2]:
        raise RuntimeError('published SCORM component fields do not match the fixture')
    package = _verify_package(scorm_block)
    return course, blocks, package


def provision(fixture):
    source = _scorm_source_identity(fixture)
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
            course = store.update_item(course, author.id)

            parent_location = course.location
            for block_type, block_id, display_name in BLOCKS:
                fields = {'display_name': display_name}
                if block_type == 'scormxblock':
                    fields.update({
                        'has_score': False,
                        'open_new_tab': False,
                        'scorm_pkg': PACKAGE_INDEX,
                        'scorm_pkg_filename': 'p1b-scorm-render.zip',
                        'scorm_pkg_version': 'SCORM12',
                        'scorm_pkg_modified': timezone.now(),
                        'instruction': 'P1-B isolated SCORM 1.2 render fixture',
                    })
                block = _get_or_create_child(
                    store,
                    parent_location,
                    course_key,
                    author.id,
                    block_type,
                    block_id,
                    fields,
                )
                if block_type == 'scormxblock':
                    _write_package(block)
                    block = store.update_item(block, author.id)
                parent_location = block.location
            store.publish(course.location, author.id)

    published_course, published_blocks, package = _published_fixture(store, fixture)
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
        defaults={'name': 'P1-B SCORM {}'.format(fixture['runtime'])},
    )
    site.name = 'P1-B SCORM {}'.format(fixture['runtime'])
    site.save()
    site_configuration, _ = SiteConfiguration.objects.get_or_create(
        site=site,
        defaults={'enabled': True, 'values': {}},
    )
    site_values = dict(site_configuration.values or {})
    site_values.update({'course_org_filter': course_key.org, 'ENABLE_LAST_ACTIVITY': True})
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
        'package': package,
        'scorm_source': source,
        'platform_commit': os.environ.get('PY36_R1_SCORM_PLATFORM_COMMIT'),
        'platform_tree': os.environ.get('PY36_R1_SCORM_PLATFORM_TREE'),
    }, sort_keys=True)))


def reset_and_preflight(fixture):
    course_key = fixture['course_key_object']
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    learner.is_staff = False
    learner.is_superuser = False
    learner.is_active = True
    learner.save()
    CourseAccessRole.objects.filter(user=learner, org=course_key.org).delete()

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

    enrollment = CourseEnrollment.enroll(
        learner,
        course_key,
        mode=CourseMode.AUDIT,
        origin=EnrollmentOrigin.BATCH,
    )
    if enrollment.completion_date is not None:
        enrollment.completion_date = None
        enrollment.save(update_fields=['completion_date'])

    # Enrollment signals may populate derived state; each browser attempt starts render-only.
    StudentModule.objects.filter(student=learner, course_id=course_key).delete()
    BlockCompletion.objects.filter(user=learner, course_key=course_key).delete()
    PersistentCourseGrade.objects.filter(user_id=learner.id, course_id=course_key).delete()
    PersistentCourseProgress.objects.filter(user_id=learner.id, course_id=course_key).delete()

    if not CourseEnrollment.is_enrolled(learner, course_key):
        raise RuntimeError('learner is not enrolled after fixture reset')
    if enrollment.mode != CourseMode.AUDIT or enrollment.origin != EnrollmentOrigin.BATCH:
        raise RuntimeError('learner enrollment does not match the gate-owned audit fixture')
    if CourseAccessRole.objects.filter(user=learner, org=course_key.org).exists():
        raise RuntimeError('learner retains course access after reset')
    if StudentModule.objects.filter(student=learner, course_id=course_key).exists():
        raise RuntimeError('learner courseware state remains after reset')
    if BlockCompletion.objects.filter(user=learner, course_key=course_key).exists():
        raise RuntimeError('learner completion remains after reset')

    source = _scorm_source_identity(fixture)
    published_course, published_blocks, package = _published_fixture(modulestore(), fixture)
    overview = CourseOverview.load_from_module_store(course_key)
    clear_course_from_cache(course_key)
    modes = CourseMode.modes_for_course_dict(course_key)
    auto_mode = CourseMode.auto_enroll_mode(course_key, modes)
    if not CourseMode.can_auto_enroll(course_key, modes) or auto_mode != CourseMode.AUDIT:
        raise RuntimeError('course is not open for audit auto-enrollment')
    if published_course.id != course_key or overview.course_status != COURSE_RELEASED_STATUS:
        raise RuntimeError('published SCORM course is not readable')

    print('PRECONDITION_OK {}'.format(json.dumps({
        'runtime': fixture['runtime'],
        'attempt': fixture['attempt'],
        'namespace': fixture['namespace'],
        'username': learner.username,
        'course_key': text_type(course_key),
        'published_unit': text_type(published_blocks[2].location),
        'published_component': text_type(published_blocks[3].location),
        'is_enrolled': True,
        'enrollment_mode': enrollment.mode,
        'enrollment_origin': enrollment.origin,
        'courseware_state_count': 0,
        'block_completion_count': 0,
        'auto_enroll_mode': auto_mode,
        'package': package,
        'scorm_source': source,
    }, sort_keys=True)))


def postflight(fixture):
    course_key = fixture['course_key_object']
    learner = User.objects.get(username=fixture['username'], email=fixture['email'])
    enrollment = CourseEnrollment.objects.get(user=learner, course_id=course_key)
    if (
            not enrollment.is_active or
            enrollment.mode != CourseMode.AUDIT or
            enrollment.origin != EnrollmentOrigin.BATCH
    ):
        raise RuntimeError('active audit/batch enrollment is missing')
    roles = list(CourseAccessRole.objects.filter(user=learner, org=course_key.org))
    if learner.is_staff or learner.is_superuser or roles:
        raise RuntimeError('learner gained administrative access: {!r}'.format(roles))
    if enrollment.completion_date is not None:
        raise RuntimeError('render-only gate wrote an enrollment completion date')
    if BlockCompletion.objects.filter(user=learner, course_key=course_key).exists():
        raise RuntimeError('render-only gate wrote block completion')
    if PersistentCourseGrade.objects.filter(user_id=learner.id, course_id=course_key).exists():
        raise RuntimeError('render-only gate wrote persistent grade state')
    if PersistentCourseProgress.objects.filter(user_id=learner.id, course_id=course_key).exists():
        raise RuntimeError('render-only gate wrote persistent progress state')

    published_course, published_blocks, package = _published_fixture(modulestore(), fixture)
    accessible = get_course_with_access(learner, 'load', course_key)
    if accessible.id != published_course.id:
        raise RuntimeError('enrolled learner cannot read the published SCORM course')
    state_count = StudentModule.objects.filter(student=learner, course_id=course_key).count()
    if state_count != 3:
        raise RuntimeError(
            'expected exactly three SCORM render/runtime StudentModule rows, got {}'.format(state_count)
        )

    print('POSTCONDITION_OK {}'.format(json.dumps({
        'runtime': fixture['runtime'],
        'attempt': fixture['attempt'],
        'namespace': fixture['namespace'],
        'username': learner.username,
        'course_key': text_type(course_key),
        'is_active': enrollment.is_active,
        'mode': enrollment.mode,
        'origin': enrollment.origin,
        'completion_date': None,
        'block_completion_count': 0,
        'persistent_grade_count': 0,
        'persistent_progress_count': 0,
        'student_module_count': state_count,
        'published_component': text_type(published_blocks[3].location),
        'package': package,
        'marker': MARKER,
        'api_marker': API_MARKER,
    }, sort_keys=True)))


def identity(fixture):
    print('IDENTITY_OK {}'.format(json.dumps({
        'runtime': fixture['runtime'],
        'namespace': fixture['namespace'],
        'scorm_source': _scorm_source_identity(fixture),
        'platform_commit': os.environ.get('PY36_R1_SCORM_PLATFORM_COMMIT'),
        'platform_tree': os.environ.get('PY36_R1_SCORM_PLATFORM_TREE'),
    }, sort_keys=True)))


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('identity', 'provision', 'preflight', 'postflight'):
        raise SystemExit('usage: {} {{identity|provision|preflight|postflight}}'.format(sys.argv[0]))
    fixture = _fixture()
    actions = {
        'identity': identity,
        'provision': provision,
        'preflight': reset_and_preflight,
        'postflight': postflight,
    }
    actions[sys.argv[1]](fixture)


if __name__ == '__main__':
    main()
