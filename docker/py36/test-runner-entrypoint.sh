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
        "${RUNNER_PLATFORM_ROOT}/common/lib/capa/setup.py"
fi

export PYTHONPATH="/opt/runner:${RUNNER_METADATA_ROOT}:${RUNNER_PLATFORM_ROOT}:${RUNNER_PLATFORM_ROOT}/common/lib/xmodule:${RUNNER_PLATFORM_ROOT}/common/lib/capa:${RUNNER_PLATFORM_ROOT}/common/lib/calc:${RUNNER_PLATFORM_ROOT}/common/lib/safe_lxml:${RUNNER_PLATFORM_ROOT}/common/lib/symmath:${RUNNER_PLATFORM_ROOT}/common/lib/chem:${RUNNER_PLATFORM_ROOT}/common/lib/dogstats${PYTHONPATH:+:${PYTHONPATH}}"
export DJANGO_SETTINGS_MODULE="py36_r1_test_settings"
export DISABLE_MIGRATIONS="${DISABLE_MIGRATIONS:-1}"
export EDXAPP_TEST_MONGO_HOST="${EDXAPP_TEST_MONGO_HOST:-edx.devstack.mongo}"
export EDXAPP_TEST_MONGO_PORT="${EDXAPP_TEST_MONGO_PORT:-27017}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
export PY36_R1_TEST_NAMESPACE="${RUNNER_NAMESPACE}"
export PY36_R1_TEST_ROOT="${PY36_R1_TEST_ROOT:-/runner/test_root}"

mkdir -p "${PY36_R1_TEST_ROOT}/db" "${PY36_R1_TEST_ROOT}/data" "${PY36_R1_TEST_ROOT}/uploads"
mkdir -p /edx/var/log/cms
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
    all)
        print_identity
        collect_target "lms/djangoapps/static_template_view/tests/test_views.py"
        collect_target "common/lib/xmodule/xmodule/tests/test_raw_module.py"
        ;;
    *)
        echo "usage: $0 {identity|lms|xmodule|focused|p1b-batch1-collect|p1b-batch1|all}" >&2
        exit 2
        ;;
esac
