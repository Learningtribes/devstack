#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
DEVSTACK_ROOT=$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd -P)
HARNESS_ROOT=${PY36_R1_ORA2_HARNESS_ROOT:-/Users/noahwang/workspace/hawthorn/platform-browser-acceptance-harness}
HARNESS_SKILL_ROOT=${HARNESS_ROOT}/.claude/skills/browser-acceptance
SERVICE_RUNNER=${SCRIPT_DIR}/run-p1b-ora2-assessment-service.sh
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
        PORT=18145
        USERNAME=qaora2_py36
        EMAIL=qaora2_py36@example.com
        STAFF_USERNAME=qaora2staff_py36
        STAFF_EMAIL=qaora2staff_py36@example.com
        COURSE_KEY=course-v1:QA+ORA2Assessment+Py36
        BLOCK_ID=p1b_ora2_staff_py36
        LOG_RUNTIME=py36-service-r17
        ;;
    py27)
        PORT=18146
        USERNAME=qaora2_py27
        EMAIL=qaora2_py27@example.com
        STAFF_USERNAME=qaora2staff_py27
        STAFF_EMAIL=qaora2staff_py27@example.com
        COURSE_KEY=course-v1:QA+ORA2Assessment+Py27
        BLOCK_ID=p1b_ora2_staff_py27
        LOG_RUNTIME=py27-service-r2
        ;;
esac

LOG_ROOT=${PY36_R1_ORA2_LOG_ROOT:-/tmp/py36-p1b-ora2-assessment-20260804/${LOG_RUNTIME}}
EVIDENCE_DIR=${LOG_ROOT}/browser/attempt${ATTEMPT}
HANDSHAKE_DIR=${EVIDENCE_DIR}/handshakes
PLAYWRIGHT_OUTPUT=${EVIDENCE_DIR}/playwright-output
STATE_FILE=${EVIDENCE_DIR}/${RUNTIME}-attempt${ATTEMPT}-browser-state.json
RESPONSE_MARKER=ORA2_RESPONSE_${RUNTIME}_A${ATTEMPT}
FEEDBACK_MARKER=ORA2_FEEDBACK_${RUNTIME}_A${ATTEMPT}
SUBMISSION_REQUEST=${HANDSHAKE_DIR}/submission-request.json
SUBMISSION_RELEASE=${HANDSHAKE_DIR}/submission-release.json
LEASE_REQUEST=${HANDSHAKE_DIR}/lease-request.json
LEASE_RELEASE=${HANDSHAKE_DIR}/lease-release.json
POST_REQUEST=${HANDSHAKE_DIR}/postcondition-request.json
POST_RELEASE=${HANDSHAKE_DIR}/postcondition-release.json

test -x "${SERVICE_RUNNER}"
test -d "${HARNESS_SKILL_ROOT}/node_modules"
command -v jq >/dev/null 2>&1
if [ -e "${EVIDENCE_DIR}" ]; then
    echo "refusing to overwrite browser evidence: ${EVIDENCE_DIR}" >&2
    exit 2
fi
LMS_READY_STATUS=$(curl -sS --connect-timeout 2 --max-time 5 -o /dev/null -w '%{http_code}' \
    "http://localhost:${PORT}/login" || true)
if [ "${LMS_READY_STATUS}" != "200" ]; then
    echo "ORA2 LMS login is not ready at http://localhost:${PORT}: status=${LMS_READY_STATUS}" >&2
    exit 1
fi

mkdir -p "${HANDSHAKE_DIR}"

run_gate_action() {
    gate_action=$1
    action_log=$2
    PY36_R1_ORA2_ATTEMPT=${ATTEMPT} \
    PY36_R1_ORA2_RESPONSE_MARKER=${RESPONSE_MARKER} \
    PY36_R1_ORA2_FEEDBACK_MARKER=${FEEDBACK_MARKER} \
        "${SERVICE_RUNNER}" "${RUNTIME}" "${gate_action}" >"${action_log}" 2>&1
}

PRECONDITION_LOG=${EVIDENCE_DIR}/${RUNTIME}-attempt${ATTEMPT}-precondition.log
OFFSET_LMS=${LOG_ROOT}/handshakes/attempt${ATTEMPT}-lms.offset
OFFSET_WORKER=${LOG_ROOT}/handshakes/attempt${ATTEMPT}-worker.offset
if [ -e "${OFFSET_LMS}" ] || [ -e "${OFFSET_WORKER}" ]; then
    if [ ! -s "${OFFSET_LMS}" ] || [ ! -s "${OFFSET_WORKER}" ]; then
        echo "incomplete attempt log-offset handshake" >&2
        exit 1
    fi
    EXISTING_PREFLIGHT=${LOG_ROOT}/preflight-attempt${ATTEMPT}.log
    if [ ! -s "${EXISTING_PREFLIGHT}" ] || ! rg -q "^PRECONDITION_OK .*\"attempt\": ${ATTEMPT}([,}])" "${EXISTING_PREFLIGHT}"; then
        echo "attempt offsets exist without matching PRECONDITION_OK evidence" >&2
        exit 1
    fi
    cp "${EXISTING_PREFLIGHT}" "${PRECONDITION_LOG}"
else
    run_gate_action preflight "${PRECONDITION_LOG}"
fi
if ! rg -q '^PRECONDITION_OK ' "${PRECONDITION_LOG}"; then
    cat "${PRECONDITION_LOG}" >&2
    exit 1
fi

wait_for_request() {
    request_file=$1
    waited=0
    while [ ! -s "${request_file}" ]; do
        if [ "${waited}" -ge 180 ]; then
            echo "timed out waiting for browser handshake: ${request_file}" >&2
            return 1
        fi
        sleep 1
        waited=$((waited + 1))
    done
}

release_action() {
    request_file=$1
    release_file=$2
    gate_action=$3
    expected_label=$4
    action_log=${EVIDENCE_DIR}/${RUNTIME}-attempt${ATTEMPT}-${gate_action}.log
    response_json=${action_log}.json
    wait_for_request "${request_file}"
    jq -e \
        --arg runtime "${RUNTIME}" \
        --arg attempt "${ATTEMPT}" \
        '.runtime == $runtime and (.attempt | tostring) == $attempt' \
        "${request_file}" >/dev/null
    run_gate_action "${gate_action}" "${action_log}"
    matching_lines=$(rg -c "^${expected_label} " "${action_log}" || true)
    if [ "${matching_lines}" != "1" ]; then
        cat "${action_log}" >&2
        return 1
    fi
    sed -n "s/^${expected_label} //p" "${action_log}" | \
        jq -e --arg status "${expected_label}" '. + {status: $status}' >"${response_json}"
    mv "${response_json}" "${release_file}"
}

watch_handshakes() {
    release_action "${SUBMISSION_REQUEST}" "${SUBMISSION_RELEASE}" submission-ready SUBMISSION_READY_OK
    release_action "${LEASE_REQUEST}" "${LEASE_RELEASE}" staff-lease STAFF_LEASE_OK
    release_action "${POST_REQUEST}" "${POST_RELEASE}" postflight POSTCONDITION_OK
    printf '%s\n' "HANDSHAKES_OK runtime=${RUNTIME} attempt=${ATTEMPT}"
}

watch_handshakes >"${EVIDENCE_DIR}/handshake-watcher.log" 2>&1 &
WATCHER_PID=$!
cleanup_watcher() {
    if kill -0 "${WATCHER_PID}" >/dev/null 2>&1; then
        kill "${WATCHER_PID}" >/dev/null 2>&1 || true
    fi
    wait "${WATCHER_PID}" >/dev/null 2>&1 || true
}
trap cleanup_watcher EXIT INT TERM HUP

set +e
(
    cd "${HARNESS_SKILL_ROOT}"
    BROWSER_ACCEPTANCE_BASE_URL=http://localhost:${PORT} \
    BROWSER_ORA2_RUNTIME=${RUNTIME} \
    BROWSER_ORA2_ATTEMPT=${ATTEMPT} \
    BROWSER_ORA2_USERNAME=${USERNAME} \
    BROWSER_ORA2_EMAIL=${EMAIL} \
    BROWSER_ORA2_STAFF_USERNAME=${STAFF_USERNAME} \
    BROWSER_ORA2_STAFF_EMAIL=${STAFF_EMAIL} \
    BROWSER_ORA2_COURSE_KEY=${COURSE_KEY} \
    BROWSER_ORA2_BLOCK_ID=${BLOCK_ID} \
    BROWSER_ORA2_RESPONSE_MARKER=${RESPONSE_MARKER} \
    BROWSER_ORA2_FEEDBACK_MARKER=${FEEDBACK_MARKER} \
    BROWSER_ORA2_EVIDENCE_DIR=${EVIDENCE_DIR} \
    BROWSER_ORA2_STATE_FILE=${STATE_FILE} \
    BROWSER_ORA2_SUBMISSION_REQUEST=${SUBMISSION_REQUEST} \
    BROWSER_ORA2_SUBMISSION_RELEASE=${SUBMISSION_RELEASE} \
    BROWSER_ORA2_LEASE_REQUEST=${LEASE_REQUEST} \
    BROWSER_ORA2_LEASE_RELEASE=${LEASE_RELEASE} \
    BROWSER_ORA2_POST_REQUEST=${POST_REQUEST} \
    BROWSER_ORA2_POST_RELEASE=${POST_RELEASE} \
        npx playwright test tests/ora2_assessment.spec.ts \
            --workers=1 --retries=0 --trace=retain-on-failure --output="${PLAYWRIGHT_OUTPUT}"
) >"${EVIDENCE_DIR}/playwright.log" 2>&1
PLAYWRIGHT_STATUS=$?
set -e
printf '%s\n' "${PLAYWRIGHT_STATUS}" >"${EVIDENCE_DIR}/playwright.exit"

if [ "${PLAYWRIGHT_STATUS}" -ne 0 ]; then
    cleanup_watcher
    trap - EXIT INT TERM HUP
    tail -n 160 "${EVIDENCE_DIR}/handshake-watcher.log" >&2 || true
    tail -n 240 "${EVIDENCE_DIR}/playwright.log" >&2 || true
    exit "${PLAYWRIGHT_STATUS}"
fi
if ! wait "${WATCHER_PID}"; then
    trap - EXIT INT TERM HUP
    cat "${EVIDENCE_DIR}/handshake-watcher.log" >&2
    exit 1
fi
trap - EXIT INT TERM HUP

jq -e \
    --arg runtime "${RUNTIME}" \
    --arg attempt "${ATTEMPT}" \
    '.status == "BROWSER_ORA2_OK" and .runtime == $runtime and .attempt == $attempt' \
    "${STATE_FILE}" >/dev/null
test "$(rg -c '^HANDSHAKES_OK ' "${EVIDENCE_DIR}/handshake-watcher.log")" = "1"
printf '%s\n' \
    "BROWSER_ATTEMPT_OK runtime=${RUNTIME} attempt=${ATTEMPT}" \
    "evidence_dir=${EVIDENCE_DIR}" \
    "state_file=${STATE_FILE}"
