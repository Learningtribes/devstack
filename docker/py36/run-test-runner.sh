#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
RUNNER_KIND="${1:-}"
RUNNER_TARGET="${2:-identity}"

case "${RUNNER_KIND}" in
    py36)
        RUNNER_IMAGE="${PY36_R1_PY36_RUNNER_IMAGE:-ltdps/edxapp@sha256:5d96c0bf61010557bfc6c8959a72d56384fe7748f5c22023aa33b3f8f6e57cec}"
        RUNNER_NAMESPACE="${PY36_R1_TEST_NAMESPACE:-py36-r1-p1b-batch2-py36}"
        ;;
    py27)
        RUNNER_IMAGE="${PY36_R1_PY27_RUNNER_IMAGE:-ltdps/edxapp:py36-r1-p1b-py27-runner-batch2-r2-20260802}"
        RUNNER_NAMESPACE="${PY36_R1_TEST_NAMESPACE:-py36-r1-p1b-batch2-py27}"
        ;;
    *)
        echo "usage: $0 {py36|py27} {identity|lms|xmodule|focused|p1b-batch1-collect|p1b-batch1|p1b-batch2-collect|p1b-batch2|p1b-dashboard-remediation-collect|p1b-dashboard-remediation|p1b-grading-mutation-collect|p1b-grading-mutation|p1b-enrollment-view-targeted|p1b-discussion-read-write-collect|p1b-discussion-read-write|p1b-studio-cms-collect|p1b-studio-cms|all}" >&2
        exit 2
        ;;
esac

SOURCE_INPUT="${PLATFORM_INTEGRATION_ROOT:-${SCRIPT_DIR}/../../../platform-py3-integration}"
SOURCE_ROOT=$(CDPATH= cd -- "${SOURCE_INPUT}" && pwd -P)
PROTECTED_ROOT=/Users/noahwang/workspace/hawthorn/platform

if [ "$(basename -- "${SOURCE_ROOT}")" != "platform-py3-integration" ] || [ "${SOURCE_ROOT}" = "${PROTECTED_ROOT}" ]; then
    echo "refusing to mount a source other than platform-py3-integration: ${SOURCE_ROOT}" >&2
    exit 2
fi

exec docker run --rm \
    --network devstack_default \
    --read-only \
    --tmpfs /runner:rw,exec,size=1g \
    --tmpfs /tmp:rw,exec,size=1g \
    --tmpfs /edx/var/log:rw,exec,size=64m \
    --mount "type=bind,src=${SOURCE_ROOT},dst=/edx/app/edxapp/edx-platform,readonly" \
    --mount "type=bind,src=${SCRIPT_DIR}/test-runner-entrypoint.sh,dst=/opt/runner/test-runner-entrypoint.sh,readonly" \
    --mount "type=bind,src=${SCRIPT_DIR}/py36_r1_test_settings.py,dst=/opt/runner/py36_r1_test_settings.py,readonly" \
    --env "PY36_R1_TEST_NAMESPACE=${RUNNER_NAMESPACE}" \
    --env "PY36_R1_MONGO_DB_PREFIX=${RUNNER_NAMESPACE}" \
    --env EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo \
    --env EDXAPP_TEST_MONGO_PORT=27017 \
    --env DISABLE_MIGRATIONS=1 \
    --env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
    "${RUNNER_IMAGE}" "${RUNNER_TARGET}"
