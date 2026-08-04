#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
HARNESS_ROOT=${PY36_R1_SCORM_HARNESS_ROOT:-/Users/noahwang/workspace/hawthorn/platform-browser-acceptance-harness}
HARNESS_SKILL_ROOT=${HARNESS_ROOT}/.claude/skills/browser-acceptance
SERVICE_RUNNER=${SCRIPT_DIR}/run-p1b-scorm-render-service.sh
RUNTIME=${1:-}
ATTEMPT=${2:-}

case "${RUNTIME}:${ATTEMPT}" in
    py36:1|py36:2|py27:1|py27:2) ;;
    *)
        echo "usage: $0 {py36|py27} {1|2}" >&2
        exit 2
        ;;
esac

case "${RUNTIME}" in
    py36)
        PORT=18147
        USERNAME=qascorm_py36
        EMAIL=qascorm_py36@example.com
        COURSE_KEY=course-v1:QA+SCORMRender+Py36
        LOG_RUNTIME=py36-service-r4
        ;;
    py27)
        PORT=18148
        USERNAME=qascorm_py27
        EMAIL=qascorm_py27@example.com
        COURSE_KEY=course-v1:QA+SCORMRender+Py27
        LOG_RUNTIME=py27-service-r4
        ;;
esac

LOG_ROOT=${PY36_R1_SCORM_LOG_ROOT:-/tmp/py36-p1b-scorm-render-20260804/${LOG_RUNTIME}}
EVIDENCE_DIR=${LOG_ROOT}/browser/attempt${ATTEMPT}
PLAYWRIGHT_OUTPUT=${EVIDENCE_DIR}/playwright-output
STATE_FILE=${EVIDENCE_DIR}/${RUNTIME}-attempt${ATTEMPT}-browser-state.json
LMS_LOG=${LOG_ROOT}/lms.log

test -x "${SERVICE_RUNNER}"
test -d "${HARNESS_SKILL_ROOT}/node_modules"
command -v jq >/dev/null 2>&1
if [ -e "${EVIDENCE_DIR}" ]; then
    echo "refusing to overwrite browser evidence: ${EVIDENCE_DIR}" >&2
    exit 2
fi
login_status=$(curl -sS --connect-timeout 2 --max-time 5 -o /dev/null -w '%{http_code}' \
    "http://localhost:${PORT}/login" || true)
if [ "${login_status}" != "200" ]; then
    echo "SCORM LMS login is not ready at http://localhost:${PORT}: status=${login_status}" >&2
    exit 1
fi

mkdir -p "${EVIDENCE_DIR}"
PRECONDITION_LOG=${EVIDENCE_DIR}/${RUNTIME}-attempt${ATTEMPT}-precondition.log
PY36_R1_SCORM_ATTEMPT=${ATTEMPT} \
    "${SERVICE_RUNNER}" "${RUNTIME}" preflight >"${PRECONDITION_LOG}" 2>&1
if ! rg -q '^PRECONDITION_OK ' "${PRECONDITION_LOG}"; then
    cat "${PRECONDITION_LOG}" >&2
    exit 1
fi

test -f "${LMS_LOG}"
LMS_OFFSET=$(wc -c <"${LMS_LOG}" | tr -d ' ')
printf '%s\n' "${LMS_OFFSET}" >"${EVIDENCE_DIR}/lms-log.offset"

set +e
(
    cd "${HARNESS_SKILL_ROOT}"
    BROWSER_ACCEPTANCE_BASE_URL=http://localhost:${PORT} \
    BROWSER_SCORM_RUNTIME=${RUNTIME} \
    BROWSER_SCORM_ATTEMPT=${ATTEMPT} \
    BROWSER_SCORM_USERNAME=${USERNAME} \
    BROWSER_SCORM_EMAIL=${EMAIL} \
    BROWSER_SCORM_COURSE_KEY=${COURSE_KEY} \
    BROWSER_SCORM_EVIDENCE_DIR=${EVIDENCE_DIR} \
    BROWSER_SCORM_STATE_FILE=${STATE_FILE} \
        npx playwright test tests/scorm_render.spec.ts \
            --workers=1 --retries=0 --trace=retain-on-failure --output="${PLAYWRIGHT_OUTPUT}"
) >"${EVIDENCE_DIR}/playwright.log" 2>&1
PLAYWRIGHT_STATUS=$?
set -e
printf '%s\n' "${PLAYWRIGHT_STATUS}" >"${EVIDENCE_DIR}/playwright.exit"
if [ "${PLAYWRIGHT_STATUS}" -ne 0 ]; then
    tail -n 240 "${EVIDENCE_DIR}/playwright.log" >&2 || true
    exit "${PLAYWRIGHT_STATUS}"
fi

POSTCONDITION_LOG=${EVIDENCE_DIR}/${RUNTIME}-attempt${ATTEMPT}-postcondition.log
PY36_R1_SCORM_ATTEMPT=${ATTEMPT} \
    "${SERVICE_RUNNER}" "${RUNTIME}" postflight >"${POSTCONDITION_LOG}" 2>&1
if ! rg -q '^POSTCONDITION_OK ' "${POSTCONDITION_LOG}"; then
    cat "${POSTCONDITION_LOG}" >&2
    exit 1
fi

LOG_TAIL=${EVIDENCE_DIR}/${RUNTIME}-attempt${ATTEMPT}-lms.log
tail -c +$((LMS_OFFSET + 1)) "${LMS_LOG}" >"${LOG_TAIL}"
LOG_FINDINGS=${EVIDENCE_DIR}/${RUNTIME}-attempt${ATTEMPT}-log-findings.txt
rg -n 'Traceback|Internal Server Error|(^|[[:space:]])ERROR([[:space:]]|:)|"[[:space:]]5[0-9][0-9][[:space:]]' \
    "${LOG_TAIL}" >"${LOG_FINDINGS}" || true
if [ -s "${LOG_FINDINGS}" ]; then
    cat "${LOG_FINDINGS}" >&2
    exit 1
fi

jq -e \
    --arg runtime "${RUNTIME}" \
    --arg attempt "${ATTEMPT}" \
    '.status == "BROWSER_SCORM_OK" and .runtime == $runtime and (.attempt | tostring) == $attempt and .api.initialized == "true" and .transport.pingCount == 1' \
    "${STATE_FILE}" >/dev/null

printf '%s\n' \
    "BROWSER_SCORM_ATTEMPT_OK runtime=${RUNTIME} attempt=${ATTEMPT}" \
    "evidence_dir=${EVIDENCE_DIR}" \
    "state_file=${STATE_FILE}"
