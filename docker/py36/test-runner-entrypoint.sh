#!/bin/sh
set -eu

RUNNER_PLATFORM_ROOT="${RUNNER_PLATFORM_ROOT:-/edx/app/edxapp/edx-platform}"
RUNNER_PYTHON="${RUNNER_PYTHON:-python}"
RUNNER_NAMESPACE="${PY36_R1_TEST_NAMESPACE:-py36-r1-p0b}"

if [ ! -r "${RUNNER_PLATFORM_ROOT}/setup.cfg" ]; then
    echo "runner source is missing or is not the integration Platform checkout: ${RUNNER_PLATFORM_ROOT}" >&2
    exit 2
fi

export PYTHONPATH="/opt/runner:${RUNNER_PLATFORM_ROOT}:${RUNNER_PLATFORM_ROOT}/common/lib/xmodule:${RUNNER_PLATFORM_ROOT}/common/lib/capa:${RUNNER_PLATFORM_ROOT}/common/lib/calc:${RUNNER_PLATFORM_ROOT}/common/lib/safe_lxml:${RUNNER_PLATFORM_ROOT}/common/lib/symmath:${RUNNER_PLATFORM_ROOT}/common/lib/chem:${RUNNER_PLATFORM_ROOT}/common/lib/dogstats${PYTHONPATH:+:${PYTHONPATH}}"
export DJANGO_SETTINGS_MODULE="py36_r1_test_settings"
export DISABLE_MIGRATIONS="${DISABLE_MIGRATIONS:-1}"
export EDXAPP_TEST_MONGO_HOST="${EDXAPP_TEST_MONGO_HOST:-edx.devstack.mongo}"
export EDXAPP_TEST_MONGO_PORT="${EDXAPP_TEST_MONGO_PORT:-27017}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD="${PYTEST_DISABLE_PLUGIN_AUTOLOAD:-1}"
export PY36_R1_TEST_NAMESPACE="${RUNNER_NAMESPACE}"
export PY36_R1_TEST_ROOT="${PY36_R1_TEST_ROOT:-/runner/test_root}"

mkdir -p "${PY36_R1_TEST_ROOT}/db" "${PY36_R1_TEST_ROOT}/data" "${PY36_R1_TEST_ROOT}/uploads"
cd /runner

print_identity() {
    "${RUNNER_PYTHON}" -c 'import pkg_resources, sys; sys.stdout.write("python=%s\n" % sys.version.split()[0]); sys.stdout.write("python_executable=%s\n" % sys.executable); [sys.stdout.write("%s=%s\n" % (name, pkg_resources.get_distribution(name).version)) for name in ("pytest", "pytest-django", "ddt", "mock")]'
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
    all)
        print_identity
        collect_target "lms/djangoapps/static_template_view/tests/test_views.py"
        collect_target "common/lib/xmodule/xmodule/tests/test_raw_module.py"
        ;;
    *)
        echo "usage: $0 {identity|lms|xmodule|all}" >&2
        exit 2
        ;;
esac
