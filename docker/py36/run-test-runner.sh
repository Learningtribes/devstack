#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
RUNNER_KIND="${1:-}"
RUNNER_TARGET="${2:-identity}"

case "${RUNNER_KIND}" in
    py36)
        RUNNER_IMAGE="${PY36_R1_PY36_RUNNER_IMAGE:-ltdps/edxapp:py36-r1-p0c-py36-runner-nose2-20260731}"
        RUNNER_NAMESPACE="${PY36_R1_TEST_NAMESPACE:-py36-r1-p0c-py36}"
        ;;
    py27)
        RUNNER_IMAGE="${PY36_R1_PY27_RUNNER_IMAGE:-ltdps/edxapp:py36-r1-p0c-py27-runner-wiki3-20260731}"
        RUNNER_NAMESPACE="${PY36_R1_TEST_NAMESPACE:-py36-r1-p0c-py27}"
        ;;
    *)
        echo "usage: $0 {py36|py27} {identity|lms|xmodule|focused|all}" >&2
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
    --mount "type=bind,src=${SOURCE_ROOT},dst=/edx/app/edxapp/edx-platform,readonly" \
    --env "PY36_R1_TEST_NAMESPACE=${RUNNER_NAMESPACE}" \
    --env "PY36_R1_MONGO_DB_PREFIX=${RUNNER_NAMESPACE}" \
    --env EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo \
    --env EDXAPP_TEST_MONGO_PORT=27017 \
    --env DISABLE_MIGRATIONS=1 \
    --env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
    "${RUNNER_IMAGE}" "${RUNNER_TARGET}"
