#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
RUNNER_KIND="${1:-}"
RUNNER_TARGET="${2:-identity}"

case "${RUNNER_KIND}" in
    py36)
        RUNNER_IMAGE="${PY36_R2_PY36_RUNNER_IMAGE:-ltdps/edxapp:py36-r2-py36-runner-20261009}"
        RUNNER_NAMESPACE="${PY36_R2_TEST_NAMESPACE:-py36-r2-e5-py36}"
        ;;
    py27)
        RUNNER_IMAGE="${PY36_R2_PY27_RUNNER_IMAGE:-ltdps/edxapp:py36-r2-py27-runner-20261009}"
        RUNNER_NAMESPACE="${PY36_R2_TEST_NAMESPACE:-py36-r2-e5-py27}"
        ;;
    *)
        echo "usage: $0 {py36|py27} {identity|r2-dcc-collect|r2-dcc|lms|xmodule|focused-collect|focused|p1b-batch1-collect|p1b-batch1|p1b-batch2-collect|p1b-batch2|p1b-learning-path-collect|p1b-learning-path|p1b-dashboard-remediation-collect|p1b-dashboard-remediation|p1b-grading-mutation-collect|p1b-grading-mutation|p1b-enrollment-view-targeted|p1b-discussion-read-write-collect|p1b-discussion-read-write|p1b-studio-cms-collect|p1b-studio-cms|p1b-ora2-assessment-collect|p1b-ora2-assessment|p1b-scorm-render-collect|p1b-scorm-render|all}" >&2
        exit 2
        ;;
esac

SOURCE_INPUT="${PLATFORM_SOURCE_ROOT:-${SCRIPT_DIR}/../../../platform-r2-py36-src}"
SOURCE_ROOT=$(CDPATH= cd -- "${SOURCE_INPUT}" && pwd -P)
ORA2_SOURCE_INPUT="${ORA2_INTEGRATION_ROOT:-${SCRIPT_DIR}/../../../edx-ora2}"
ORA2_SOURCE_ROOT=$(CDPATH= cd -- "${ORA2_SOURCE_INPUT}" && pwd -P)
PROTECTED_ROOT=/Users/noahwang/workspace/hawthorn/platform
# R2-preview PR #2401 head after the E3 fix; override only for a recorded new identity.
EXPECTED_PLATFORM_COMMIT="${EXPECTED_PLATFORM_COMMIT:-0ac3bfa6d099916cc58fc258db17221801f49d48}"
EXPECTED_PLATFORM_TREE="${EXPECTED_PLATFORM_TREE:-357effc3232a453f780d61cb9e22656fe08ca479}"

if [ "${SOURCE_ROOT}" = "${PROTECTED_ROOT}" ]; then
    echo "refusing protected Platform source: ${SOURCE_ROOT}" >&2
    exit 2
fi
if [ "$(git -C "${SOURCE_ROOT}" rev-parse HEAD)" != "${EXPECTED_PLATFORM_COMMIT}" ] || \
        [ "$(git -C "${SOURCE_ROOT}" rev-parse HEAD^{tree})" != "${EXPECTED_PLATFORM_TREE}" ] || \
        [ -n "$(git -C "${SOURCE_ROOT}" status --porcelain=v1)" ]; then
    echo "refusing non-frozen or dirty Platform source: ${SOURCE_ROOT}" >&2
    exit 2
fi

if [ "$(basename -- "${ORA2_SOURCE_ROOT}")" != "edx-ora2" ]; then
    echo "refusing to mount an unexpected ORA2 source: ${ORA2_SOURCE_ROOT}" >&2
    exit 2
fi
if [ "$(git -C "${ORA2_SOURCE_ROOT}" rev-parse HEAD)" != "d3f24a9c539528e960c8dcc9aef200cea0c49baf" ]; then
    echo "ORA2 test source is not the frozen accepted commit" >&2
    exit 2
fi
if [ -n "$(git -C "${ORA2_SOURCE_ROOT}" status --porcelain=v1)" ]; then
    echo "ORA2 test source is dirty" >&2
    exit 2
fi

# The cgroup cap keeps an OOM inside the runner instead of the shared edx.devstack.mongo.
exec docker run --rm \
    --network devstack_default \
    --memory "${PY36_R2_GATE_TEST_MEMORY:-4g}" \
    --read-only \
    --tmpfs /runner:rw,exec,size=1g \
    --tmpfs /tmp:rw,exec,size=1g \
    --tmpfs /edx/var/log:rw,exec,size=64m \
    --mount "type=bind,src=${SOURCE_ROOT},dst=/edx/app/edxapp/edx-platform,readonly" \
    --mount "type=bind,src=${ORA2_SOURCE_ROOT},dst=/runner/edx-ora2-source,readonly" \
    --mount "type=bind,src=${SCRIPT_DIR}/test-runner-entrypoint.sh,dst=/opt/runner/test-runner-entrypoint.sh,readonly" \
    --mount "type=bind,src=${SCRIPT_DIR}/py36_r1_test_settings.py,dst=/opt/runner/py36_r1_test_settings.py,readonly" \
    --env "PY36_R1_TEST_NAMESPACE=${RUNNER_NAMESPACE}" \
    --env "PY36_R1_MONGO_DB_PREFIX=${RUNNER_NAMESPACE}" \
    --env ORA2_TEST_SOURCE_ROOT=/runner/edx-ora2-source \
    --env EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo \
    --env EDXAPP_TEST_MONGO_PORT=27017 \
    --env DISABLE_MIGRATIONS=1 \
    --env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
    "${RUNNER_IMAGE}" "${RUNNER_TARGET}"
