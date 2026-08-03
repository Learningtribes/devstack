#!/bin/sh
set -eu

RUNNER_PLATFORM_ROOT="${RUNNER_PLATFORM_ROOT:-/edx/app/edxapp/edx-platform}"
RUNNER_PYTHON="${RUNNER_PYTHON:-python}"
RUNNER_NAMESPACE="${PY36_R1_TEST_NAMESPACE:-py36-r1-p0b}"
RUNNER_METADATA_ROOT="${PY36_R1_METADATA_ROOT:-/runner/source-metadata}"

if [ ! -r "${RUNNER_PLATFORM_ROOT}/setup.cfg" ]; then
    echo "runner source is missing or is not the integration Platform checkout: ${RUNNER_PLATFORM_ROOT}" >&2
    exit 2
fi

if [ "${PY36_R1_GENERATE_SOURCE_METADATA:-0}" = "1" ]; then
    "${RUNNER_PYTHON}" /opt/runner/py27_source_metadata.py \
        "${RUNNER_METADATA_ROOT}" \
        "${RUNNER_PLATFORM_ROOT}/setup.py" \
        "${RUNNER_PLATFORM_ROOT}/common/lib/xmodule/setup.py" \
        "${RUNNER_PLATFORM_ROOT}/common/lib/capa/setup.py" \
        "${RUNNER_PLATFORM_ROOT}/openedx/core/lib/xblock_builtin/xblock_discussion/setup.py"
fi

export PYTHONPATH="/opt/runner:${RUNNER_METADATA_ROOT}:${RUNNER_PLATFORM_ROOT}:${RUNNER_PLATFORM_ROOT}/common/lib/xmodule:${RUNNER_PLATFORM_ROOT}/common/lib/capa:${RUNNER_PLATFORM_ROOT}/openedx/core/lib/xblock_builtin/xblock_discussion:${RUNNER_PLATFORM_ROOT}/common/lib/calc:${RUNNER_PLATFORM_ROOT}/common/lib/safe_lxml:${RUNNER_PLATFORM_ROOT}/common/lib/symmath:${RUNNER_PLATFORM_ROOT}/common/lib/chem:${RUNNER_PLATFORM_ROOT}/common/lib/dogstats${PYTHONPATH:+:${PYTHONPATH}}"
export DJANGO_SETTINGS_MODULE="py36_r1_test_settings"
export DISABLE_MIGRATIONS="${DISABLE_MIGRATIONS:-1}"
export EDXAPP_TEST_MONGO_HOST="${EDXAPP_TEST_MONGO_HOST:-edx.devstack.mongo}"
export EDXAPP_TEST_MONGO_PORT="${EDXAPP_TEST_MONGO_PORT:-27017}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
export PY36_R1_TEST_NAMESPACE="${RUNNER_NAMESPACE}"
export PY36_R1_TEST_ROOT="${PY36_R1_TEST_ROOT:-/runner/test_root}"

mkdir -p "${PY36_R1_TEST_ROOT}/db" "${PY36_R1_TEST_ROOT}/data" "${PY36_R1_TEST_ROOT}/uploads"
mkdir -p /edx/var/log/cms /edx/var/log/lms
cd /runner

print_identity() {
    "${RUNNER_PYTHON}" -c 'import pkg_resources, sys; sys.stdout.write("python=%s\n" % sys.version.split()[0]); sys.stdout.write("python_executable=%s\n" % sys.executable); [sys.stdout.write("%s=%s\n" % (name, pkg_resources.get_distribution(name).version)) for name in ("pytest", "pytest-django", "ddt", "mock", "nose", "factory-boy", "Faker")]'
    printf '%s\n' "settings=${DJANGO_SETTINGS_MODULE}" "namespace=${RUNNER_NAMESPACE}" "mongo_host=${EDXAPP_TEST_MONGO_HOST}" "mongo_db_prefix=${PY36_R1_MONGO_DB_PREFIX:-${RUNNER_NAMESPACE}}" "source=${RUNNER_PLATFORM_ROOT}" "source_mount=read-only-required"
}

collect_target() {
    target="$1"
    target_dir=$(dirname -- "${target}")
    case "${target}" in
        common/lib/xmodule/*)
            # The selected library collection path uses Django's lazy settings
            # only for a safe default. Loading the full LMS settings here would
            # create a circular import through xmodule.modulestore.inheritance.
            unset DJANGO_SETTINGS_MODULE
            ;;
        *)
            export DJANGO_SETTINGS_MODULE="py36_r1_test_settings"
            ;;
    esac
    "${RUNNER_PYTHON}" -m pytest \
        -p no:django \
        -p no:xdist \
        -p no:xdist.looponfail \
        -p no:randomly \
        -p no:pytest_forked \
        -p no:pytest_cov \
        -p no:attrib \
        -p no:cacheprovider \
        -o addopts= \
        --confcutdir="${RUNNER_PLATFORM_ROOT}/${target_dir}" \
        --collect-only \
        --rootdir="${RUNNER_PLATFORM_ROOT}" \
        --tb=short \
        -q \
        "${RUNNER_PLATFORM_ROOT}/${target}"
}

run_batch1() {
    collection_flag=""
    case "$1" in
        collect)
            collection_flag="--collect-only"
            ;;
        execute)
            ;;
        *)
            echo "usage: run_batch1 {collect|execute}" >&2
            exit 2
            ;;
    esac

    export DJANGO_SETTINGS_MODULE="py36_r1_test_settings"
    "${RUNNER_PYTHON}" -m pytest \
        -p no:django \
        -p pytest_django.plugin \
        -p no:xdist \
        -p no:xdist.looponfail \
        -p no:randomly \
        -p no:pytest_forked \
        -p no:pytest_cov \
        -p no:attrib \
        -p no:cacheprovider \
        -o addopts= \
        --nomigrations \
        --reuse-db \
        ${collection_flag} \
        --rootdir="${RUNNER_PLATFORM_ROOT}" \
        --tb=short \
        -q \
        "${RUNNER_PLATFORM_ROOT}/openedx/core/djangoapps/request_cache/tests.py" \
        "${RUNNER_PLATFORM_ROOT}/openedx/core/lib/tests/test_cache_utils.py" \
        "${RUNNER_PLATFORM_ROOT}/openedx/core/djangoapps/safe_sessions/tests/test_middleware.py" \
        "${RUNNER_PLATFORM_ROOT}/openedx/core/djangoapps/safe_sessions/tests/test_safe_cookie_data.py" \
        "${RUNNER_PLATFORM_ROOT}/openedx/core/djangoapps/safe_sessions/tests/test_utils.py" \
        "${RUNNER_PLATFORM_ROOT}/common/djangoapps/student/tests/test_cookie_names.py" \
        "${RUNNER_PLATFORM_ROOT}/common/djangoapps/student/tests/test_cookies.py" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/metrics/tests/test_metrics.py" \
        "${RUNNER_PLATFORM_ROOT}/lms/lib/comment_client/tests/test_utils.py"
}

run_batch2() {
    collection_flag=""
    case "$1" in
        collect)
            collection_flag="--collect-only"
            ;;
        execute)
            ;;
        *)
            echo "usage: run_batch2 {collect|execute}" >&2
            exit 2
            ;;
    esac

    export DJANGO_SETTINGS_MODULE="py36_r1_test_settings"
    "${RUNNER_PYTHON}" -m pytest \
        -p no:django \
        -p pytest_django.plugin \
        -p no:xdist \
        -p no:xdist.looponfail \
        -p no:randomly \
        -p no:pytest_forked \
        -p no:pytest_cov \
        -p no:attrib \
        -p no:cacheprovider \
        -o addopts= \
        --nomigrations \
        --reuse-db \
        ${collection_flag} \
        --rootdir="${RUNNER_PLATFORM_ROOT}" \
        --tb=short \
        -q \
        "${RUNNER_PLATFORM_ROOT}/common/djangoapps/student/tests/test_enrollment.py" \
        "${RUNNER_PLATFORM_ROOT}/common/djangoapps/student/tests/test_recent_enrollments.py" \
        "${RUNNER_PLATFORM_ROOT}/common/djangoapps/student/tests/test_recent_enrollment_filter.py"
}

run_dashboard_remediation() {
    collection_flag=""
    case "$1" in
        collect)
            collection_flag="--collect-only"
            ;;
        execute)
            ;;
        *)
            echo "usage: run_dashboard_remediation {collect|execute}" >&2
            exit 2
            ;;
    esac

    export DJANGO_SETTINGS_MODULE="py36_r1_test_settings"
    "${RUNNER_PYTHON}" -m pytest \
        -p no:django \
        -p pytest_django.plugin \
        -p no:xdist \
        -p no:xdist.looponfail \
        -p no:randomly \
        -p no:pytest_forked \
        -p no:pytest_cov \
        -p no:attrib \
        -p no:cacheprovider \
        -o addopts= \
        --nomigrations \
        --reuse-db \
        ${collection_flag} \
        --rootdir="${RUNNER_PLATFORM_ROOT}" \
        --tb=short \
        -q \
        "${RUNNER_PLATFORM_ROOT}/common/djangoapps/edxmako/tests.py::UserMetadataTemplateTests" \
        "${RUNNER_PLATFORM_ROOT}/common/djangoapps/student/tests/tests.py::AnonymousLookupTable" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/courseware/tests/test_models.py" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/courseware/tests/test_utils.py" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/lms_xblock/test/test_runtime.py::TestHandlerUrl" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/grades/tests/test_models.py::BlockRecordListTestCase" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/grades/tests/test_models.py::VisibleBlocksTest" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/grades/tests/test_transformer.py::GradesTransformerTestCase::test_grading_policy_collected" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/grades/tests/test_course_grade.py::TestCourseGrade" \
        "${RUNNER_PLATFORM_ROOT}/openedx/core/lib/tests/test_graph_traversals.py" \
        "${RUNNER_PLATFORM_ROOT}/common/lib/xmodule/xmodule/tests/test_graders.py::GraderTest::test_assignment_format_grader" \
        "${RUNNER_PLATFORM_ROOT}/common/lib/xmodule/xmodule/tests/test_graders.py::GraderTest::test_assignment_format_grader_on_single_section_entry" \
        "${RUNNER_PLATFORM_ROOT}/openedx/features/course_experience/tests/test_course_tools.py"
}

run_grading_mutation() {
    collection_flag=""
    case "$1" in
        collect)
            collection_flag="--collect-only"
            ;;
        execute)
            ;;
        *)
            echo "usage: run_grading_mutation {collect|execute}" >&2
            exit 2
            ;;
    esac

    export DJANGO_SETTINGS_MODULE="py36_r1_test_settings"
    "${RUNNER_PYTHON}" -m pytest \
        -p no:django \
        -p pytest_django.plugin \
        -p no:xdist \
        -p no:xdist.looponfail \
        -p no:randomly \
        -p no:pytest_forked \
        -p no:pytest_cov \
        -p no:attrib \
        -p no:cacheprovider \
        -o addopts= \
        --nomigrations \
        --reuse-db \
        ${collection_flag} \
        --rootdir="${RUNNER_PLATFORM_ROOT}" \
        --tb=short \
        -q \
        "${RUNNER_PLATFORM_ROOT}/common/djangoapps/track/views/tests/test_views.py::TestTrackViews::test_get_request_header_handles_python_2_and_python_3_values" \
        "${RUNNER_PLATFORM_ROOT}/common/lib/capa/capa/tests/test_correctmap.py::CorrectMapTest::test_set_dict_supports_current_and_legacy_state" \
        "${RUNNER_PLATFORM_ROOT}/common/lib/capa/capa/tests/test_inputtypes.py::OptionInputTest" \
        "${RUNNER_PLATFORM_ROOT}/common/lib/capa/capa/tests/test_util.py::UtilTest::test_contextualize_text_replaces_longer_names_first" \
        "${RUNNER_PLATFORM_ROOT}/common/lib/xmodule/xmodule/tests/test_capa_module.py::CapaModuleTest::test_submit_problem_incorrect" \
        "${RUNNER_PLATFORM_ROOT}/common/lib/xmodule/xmodule/tests/test_capa_module.py::CapaModuleTest::test_answer_notifications_support_mapping_views" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/courseware/tests/test_submitting_problems.py::TestSubmittingProblems" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/grades/tests/test_signals.py::ScoreChangedSignalRelayTest" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/grades/tests/test_tasks.py::RecalculateSubsectionGradeTest" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/grades/tests/test_models.py::PersistentSubsectionGradeTest" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/grades/tests/test_models.py::PersistentCourseGradesTest" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/grades/tests/test_course_grade_factory.py::TestCourseGradeFactory" \
        "${RUNNER_PLATFORM_ROOT}/openedx/tests/completion_integration/test_handlers.py::ScorableCompletionHandlerTestCase" \
        "${RUNNER_PLATFORM_ROOT}/common/djangoapps/student/tests/test_course_grade_completion.py::HandleCourseGradeChangedTests" \
        "${RUNNER_PLATFORM_ROOT}/common/djangoapps/student/tests/test_enrollment_behavior.py::CourseEnrollmentTest"
}

run_enrollment_view_targeted() {
    export DJANGO_SETTINGS_MODULE="py36_r1_test_settings"
    "${RUNNER_PYTHON}" -m pytest \
        -p no:django \
        -p pytest_django.plugin \
        -p no:xdist \
        -p no:xdist.looponfail \
        -p no:randomly \
        -p no:pytest_forked \
        -p no:pytest_cov \
        -p no:attrib \
        -p no:cacheprovider \
        -o addopts= \
        --nomigrations \
        --reuse-db \
        --rootdir="${RUNNER_PLATFORM_ROOT}" \
        --tb=short \
        -q \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/courseware/tests/test_access_response.py" \
        "${RUNNER_PLATFORM_ROOT}/common/lib/xmodule/xmodule/tests/test_vertical.py::XModuleDescriptorHashTest" \
        "${RUNNER_PLATFORM_ROOT}/common/lib/xmodule/xmodule/tests/test_vertical.py::VerticalBlockBookmarkIdTest" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/courseware/tests/test_courses.py::CoursesTest::test_xqa_interface_template_renders_course_key" \
        "${RUNNER_PLATFORM_ROOT}/openedx/core/lib/tests/test_xblock_utils.py::TestXblockUtils::test_wrap_xblock_html_title_is_text" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/program_enrollments/tests/test_models.py"
}

run_discussion_read_write() {
    collection_flag=""
    case "$1" in
        collect)
            collection_flag="--collect-only"
            ;;
        execute)
            ;;
        *)
            echo "usage: run_discussion_read_write {collect|execute}" >&2
            exit 2
            ;;
    esac

    discussion_deps=/runner/discussion-test-deps
    if ! "${RUNNER_PYTHON}" -c 'import httpretty' >/dev/null 2>&1; then
        "${RUNNER_PYTHON}" -m pip install \
            --disable-pip-version-check \
            --no-deps \
            --target "${discussion_deps}" \
            'httpretty==0.9.5'
        export PYTHONPATH="${discussion_deps}:${PYTHONPATH}"
    fi

    export DJANGO_SETTINGS_MODULE="py36_r1_test_settings"
    "${RUNNER_PYTHON}" -m pytest \
        -p no:django \
        -p pytest_django.plugin \
        -p no:xdist \
        -p no:xdist.looponfail \
        -p no:randomly \
        -p no:pytest_forked \
        -p no:pytest_cov \
        -p no:attrib \
        -p no:cacheprovider \
        -o addopts= \
        --nomigrations \
        --reuse-db \
        ${collection_flag} \
        --rootdir="${RUNNER_PLATFORM_ROOT}" \
        --tb=short \
        -q \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/discussion/tests/test_views.py::DiscussionPython3CompatibilityTestCase" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/discussion/tests/test_views.py::ForumFormDiscussionUnicodeTestCase::test_page_render_uses_text_course_id" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/discussion/tests/test_views.py::SingleThreadTestCase" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/discussion/tests/test_views.py::DiscussionBoardFragmentViewAccessTestCase" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/discussion/tests/test_views.py::ThreadViewedEventTestCase" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/django_comment_client/tests/test_utils.py::DictionaryTestCase" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/django_comment_client/tests/test_utils.py::JsonResponseTestCase::test_json_error_accepts_text" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/django_comment_client/tests/test_utils.py::BankcardTestCase" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/django_comment_client/base/tests.py::ViewsTestCase::test_create_thread" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/django_comment_client/base/tests.py::ViewsTestCase::test_create_comment" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/django_comment_client/base/tests.py::ViewsTestCase::test_create_thread_no_title" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/django_comment_client/base/tests.py::ViewsTestCase::test_create_thread_no_body" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/django_comment_client/base/tests.py::ViewsTestCase::test_create_comment_no_body" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/django_comment_client/base/tests.py::ViewPermissionsTestCase" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/django_comment_client/base/tests.py::CreateCommentUnicodeTestCase" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/django_comment_client/base/tests.py::CreateSubCommentUnicodeTestCase" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/discussion_api/tests/test_api.py::GetThreadListTest" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/discussion_api/tests/test_api.py::CreateThreadTest" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/discussion_api/tests/test_api.py::CreateCommentTest" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/discussion_api/tests/test_api.py::RetrieveThreadTest" \
        "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/django_comment_client/base/tests.py::ForumThreadViewedEventTransformerTestCase" \
        "${RUNNER_PLATFORM_ROOT}/lms/lib/comment_client/tests/test_utils.py::CommentClientUtilsTests"
}

run_studio_cms() {
    collection_flag=""
    case "$1" in
        collect)
            collection_flag="--collect-only"
            ;;
        execute)
            ;;
        *)
            echo "usage: run_studio_cms {collect|execute}" >&2
            exit 2
            ;;
    esac

    export PY36_R1_TEST_SERVICE="cms"
    export DJANGO_SETTINGS_MODULE="py36_r1_test_settings"
    "${RUNNER_PYTHON}" -m pytest \
        -p no:django \
        -p pytest_django.plugin \
        -p no:xdist \
        -p no:xdist.looponfail \
        -p no:randomly \
        -p no:pytest_forked \
        -p no:pytest_cov \
        -p no:attrib \
        -p no:cacheprovider \
        -o addopts= \
        --nomigrations \
        --reuse-db \
        ${collection_flag} \
        --rootdir="${RUNNER_PLATFORM_ROOT}" \
        --tb=short \
        -q \
        "${RUNNER_PLATFORM_ROOT}/cms/djangoapps/contentstore/views/tests/test_item.py::TestEditItem::test_make_public" \
        "${RUNNER_PLATFORM_ROOT}/cms/djangoapps/contentstore/views/tests/test_item.py::TestEditItem::test_make_public_with_update" \
        "${RUNNER_PLATFORM_ROOT}/cms/djangoapps/contentstore/views/tests/test_item.py::TestEditItem::test_published_and_draft_contents_with_update" \
        "${RUNNER_PLATFORM_ROOT}/cms/djangoapps/contentstore/views/tests/test_item.py::TestXBlockPublishingInfo" \
        "${RUNNER_PLATFORM_ROOT}/cms/djangoapps/contentstore/views/tests/test_container_page.py::ContainerPageTestCase" \
        "${RUNNER_PLATFORM_ROOT}/cms/djangoapps/contentstore/views/tests/test_course_index.py::TestCourseIndex::test_course_staff_access" \
        "${RUNNER_PLATFORM_ROOT}/cms/djangoapps/contentstore/tests/test_permissions.py::TestCourseAccess"
}

case "${1:-identity}" in
    identity)
        print_identity
        ;;
    lms)
        collect_target "lms/djangoapps/static_template_view/tests/test_views.py"
        ;;
    xmodule)
        collect_target "common/lib/xmodule/xmodule/tests/test_raw_module.py"
        ;;
    focused)
        export DJANGO_SETTINGS_MODULE="py36_r1_test_settings"
        "${RUNNER_PYTHON}" -m pytest \
            -p no:django \
            -p pytest_django.plugin \
            -p no:xdist \
            -p no:xdist.looponfail \
            -p no:randomly \
            -p no:pytest_forked \
            -p no:pytest_cov \
            -p no:attrib \
            -p no:cacheprovider \
            -o addopts= \
            --nomigrations \
            --reuse-db \
            --rootdir="${RUNNER_PLATFORM_ROOT}" \
            --tb=short \
            -q \
            "${RUNNER_PLATFORM_ROOT}/common/djangoapps/student/tests/test_cookie_names.py" \
            "${RUNNER_PLATFORM_ROOT}/common/djangoapps/student/tests/test_recent_enrollment_filter.py" \
            "${RUNNER_PLATFORM_ROOT}/common/lib/xmodule/xmodule/tests/test_fields.py" \
            "${RUNNER_PLATFORM_ROOT}/common/lib/xmodule/xmodule/tests/test_nested_contexts.py" \
            "${RUNNER_PLATFORM_ROOT}/lms/djangoapps/metrics/tests/test_metrics.py" \
            "${RUNNER_PLATFORM_ROOT}/lms/lib/comment_client/tests/test_utils.py" \
            "${RUNNER_PLATFORM_ROOT}/openedx/core/djangoapps/safe_sessions/tests/test_middleware.py" \
            "${RUNNER_PLATFORM_ROOT}/openedx/core/djangoapps/safe_sessions/tests/test_safe_cookie_data.py"
        ;;
    p1b-batch1-collect)
        run_batch1 collect
        ;;
    p1b-batch1)
        run_batch1 execute
        ;;
    p1b-batch2-collect)
        run_batch2 collect
        ;;
    p1b-batch2)
        run_batch2 execute
        ;;
    p1b-dashboard-remediation-collect)
        run_dashboard_remediation collect
        ;;
    p1b-dashboard-remediation)
        run_dashboard_remediation execute
        ;;
    p1b-grading-mutation-collect)
        run_grading_mutation collect
        ;;
    p1b-grading-mutation)
        run_grading_mutation execute
        ;;
    p1b-enrollment-view-targeted)
        run_enrollment_view_targeted
        ;;
    p1b-discussion-read-write-collect)
        run_discussion_read_write collect
        ;;
    p1b-discussion-read-write|discussion-read-write)
        run_discussion_read_write execute
        ;;
    p1b-studio-cms-collect)
        run_studio_cms collect
        ;;
    p1b-studio-cms)
        run_studio_cms execute
        ;;
    all)
        print_identity
        collect_target "lms/djangoapps/static_template_view/tests/test_views.py"
        collect_target "common/lib/xmodule/xmodule/tests/test_raw_module.py"
        ;;
    *)
        echo "usage: $0 {identity|lms|xmodule|focused|p1b-batch1-collect|p1b-batch1|p1b-batch2-collect|p1b-batch2|p1b-dashboard-remediation-collect|p1b-dashboard-remediation|p1b-grading-mutation-collect|p1b-grading-mutation|p1b-enrollment-view-targeted|p1b-discussion-read-write-collect|p1b-discussion-read-write|p1b-studio-cms-collect|p1b-studio-cms|all}" >&2
        exit 2
        ;;
esac
