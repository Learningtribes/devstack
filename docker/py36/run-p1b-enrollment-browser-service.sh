#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
RUNTIME=${1:-}

case "${RUNTIME}" in
    py36)
        IMAGE=ltdps/edxapp:py36-r1-locked
        CONTAINER=py36-r1-p1b-enrollment-view-lms-20260802-r13
        PORT=18133
        NAMESPACE=py36_r1_p1b_enrollment_view_py36
        USERNAME=qaenroll_py36
        EMAIL=qaenroll_py36@example.com
        COURSE_KEY=course-v1:QA+EnrollmentView+Py36
        PYTHON=python
        ;;
    py27)
        IMAGE=ltdps/edxapp:py36-r1-p1b-dashboard-remediation-reviewfix-py27-20260802
        CONTAINER=py27-r1-p1b-enrollment-view-lms-20260802-r14
        PORT=18134
        NAMESPACE=py36_r1_p1b_enrollment_view_py27
        USERNAME=qaenroll_py27
        EMAIL=qaenroll_py27@example.com
        COURSE_KEY=course-v1:QA+EnrollmentView+Py27
        PYTHON=/edx/app/edxapp/venvs/edxapp/bin/python
        ;;
    *)
        echo "usage: $0 {py36|py27}" >&2
        exit 2
        ;;
esac

SOURCE_INPUT=${PLATFORM_INTEGRATION_ROOT:-${SCRIPT_DIR}/../../../platform-py3-integration}
SOURCE_ROOT=$(CDPATH= cd -- "${SOURCE_INPUT}" && pwd -P)
WORKSPACE_ROOT=$(CDPATH= cd -- "${SOURCE_ROOT}/.." && pwd -P)
LOG_ROOT=${PY36_R1_ENROLLMENT_LOG_ROOT:-/tmp/py36-p1b-enrollment-course-view-20260802/logs}
CONTROL_CONTAINER=py36-r1-p1b-dashboard-reviewfix-lms-20260802-r13

if [ "$(basename -- "${SOURCE_ROOT}")" != "platform-py3-integration" ]; then
    echo "refusing to mount a source other than platform-py3-integration: ${SOURCE_ROOT}" >&2
    exit 2
fi
if docker container inspect "${CONTAINER}" >/dev/null 2>&1; then
    echo "refusing to replace existing container: ${CONTAINER}" >&2
    exit 2
fi

AUTH_JSON=$(docker inspect "${CONTROL_CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/lms.auth.json"}}{{.Source}}{{end}}{{end}}')
ENV_JSON=$(docker inspect "${CONTROL_CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/lms.env.json"}}{{.Source}}{{end}}{{end}}')
test -f "${AUTH_JSON}"
test -f "${ENV_JSON}"
mkdir -p "${LOG_ROOT}/${RUNTIME}/cms" "${LOG_ROOT}/${RUNTIME}/lms"

COMMON_PYTHONPATH=/edx/app/edxapp:/opt/runner:/runner/source-metadata:/edx/app/edxapp/edx-platform:/edx/app/edxapp/edx-platform/common/lib/xmodule:/edx/app/edxapp/edx-platform/common/lib/capa:/edx/app/edxapp/edx-platform/common/lib/calc:/edx/app/edxapp/edx-platform/common/lib/safe_lxml:/edx/app/edxapp/edx-platform/common/lib/symmath:/edx/app/edxapp/edx-platform/common/lib/chem:/edx/app/edxapp/edx-platform/common/lib/dogstats

if [ "${RUNTIME}" = py36 ]; then
    PYTHON_CODE='import os; from openedx.core.lib.logsettings import log_python_warnings; log_python_warnings(); from safe_lxml import defuse_xml_libs; defuse_xml_libs(); import django; django.setup(); from django.core.management import execute_from_command_line; execute_from_command_line(["manage.py", "runserver", "0.0.0.0:18000", "--noreload"])'
    COMMAND="exec python -c '${PYTHON_CODE}'"
else
    COMMAND="${PYTHON} /opt/runner/py27_source_metadata.py /runner/source-metadata /edx/app/edxapp/edx-platform/setup.py /edx/app/edxapp/edx-platform/common/lib/xmodule/setup.py /edx/app/edxapp/edx-platform/common/lib/capa/setup.py && export PYTHONPATH=${COMMON_PYTHONPATH} && exec ${PYTHON} -c 'import os; from openedx.core.lib.logsettings import log_python_warnings; log_python_warnings(); from safe_lxml import defuse_xml_libs; defuse_xml_libs(); import django; django.setup(); from django.core.management import execute_from_command_line; execute_from_command_line([\"manage.py\", \"runserver\", \"0.0.0.0:18000\", \"--noreload\"])'"
fi
set -- -c "${COMMAND}"

docker run -d \
    --name "${CONTAINER}" \
    --entrypoint /bin/sh \
    --network devstack_default \
    --label io.openedx.py36-r1.gate=p1b-enrollment-course-view \
    --label "io.openedx.py36-r1.runtime=${RUNTIME}" \
    --label "io.openedx.py36-r1.namespace=${NAMESPACE}" \
    --publish "127.0.0.1:${PORT}:18000" \
    --mount "type=bind,src=${SOURCE_ROOT},dst=/edx/app/edxapp/edx-platform,readonly" \
    --mount "type=bind,src=${SOURCE_ROOT}/lms/static/js/main.js,dst=/edx/var/edxapp/staticfiles/js/main.js,readonly" \
    --mount "type=bind,src=${WORKSPACE_ROOT}/src,dst=/edx/src,readonly" \
    --mount "type=bind,src=${AUTH_JSON},dst=/edx/app/edxapp/lms.auth.json,readonly" \
    --mount "type=bind,src=${ENV_JSON},dst=/edx/app/edxapp/lms.env.json,readonly" \
    --mount "type=bind,src=${SCRIPT_DIR}/p1b_enrollment_browser_settings.py,dst=/edx/app/edxapp/p1b_enrollment_browser_settings.py,readonly" \
    --mount "type=bind,src=${SCRIPT_DIR}/provision-p1b-enrollment-course-view.py,dst=/edx/app/edxapp/provision-p1b-enrollment-course-view.py,readonly" \
    --mount "type=bind,src=${LOG_ROOT}/${RUNTIME},dst=/edx/var/log" \
    --mount type=volume,src=devstack_edxapp_lms_assets,dst=/edx/var/edxapp/staticfiles,readonly \
    --env SERVICE_VARIANT=lms \
    --env DJANGO_SETTINGS_MODULE=p1b_enrollment_browser_settings \
    --env "PYTHONPATH=${COMMON_PYTHONPATH}" \
    --env "PY36_R1_ENROLLMENT_RUNTIME=${RUNTIME}" \
    --env "PY36_R1_ENROLLMENT_USERNAME=${USERNAME}" \
    --env "PY36_R1_ENROLLMENT_EMAIL=${EMAIL}" \
    --env "PY36_R1_ENROLLMENT_COURSE_KEY=${COURSE_KEY}" \
    --env "PY36_R1_BROWSER_NAMESPACE=${NAMESPACE}" \
    --env "PY36_R1_BROWSER_SITE_DOMAIN=localhost:${PORT}" \
    --env EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo \
    --env NO_PYTHON_UNINSTALL=1 \
    "${IMAGE}" "$@"

echo "SERVICE_STARTED runtime=${RUNTIME} container=${CONTAINER} url=http://localhost:${PORT} namespace=${NAMESPACE}"
