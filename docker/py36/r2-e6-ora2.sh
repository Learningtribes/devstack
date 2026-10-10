#!/bin/sh
# R2-preview E6 ORA2 staff-assessment gate. Starts the runtime's E6 stack with
# PY36_R2_E6_WITH_BROKER=1 and the R1 provisioner as its prestart step, then
# identity -> preflight -> Chromium: learner submits -> external
# submission-ready -> staff takes the grading lease -> external staff-lease ->
# staff assesses -> external postflight (grade/progress tasks done on the
# stack's own worker) -> learner sees the score. The spec's file handshakes
# are answered here, as R1's browser wrapper does.
# usage: r2-e6-ora2.sh {py36|py27} <out-dir> [installed|source]
#   installed (default): the image's ORA2. source (py27 only): the frozen
#   ../edx-ora2 checkout through PY36_R2_E6_ORA2_SOURCE; runs as attempt 2 so
#   its markers differ from the installed run.
#   Leaves the stack running; remove it with run-r2-e6-services.sh <rt> cleanup.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
WORKSPACE=/Users/noahwang/workspace/hawthorn
RUNTIME=$1; OUT=$2; MODE=${3:-installed}
case "${RUNTIME}" in py36|py27) ;; *) echo "runtime must be py36 or py27" >&2; exit 2 ;; esac
case "${RUNTIME}" in py36) SUFFIX=Py36 ;; py27) SUFFIX=Py27 ;; esac
# Python 3.6 runs on the ORA2 runtime (base runtime + the R1 ORA2 gate's
# edx-submissions Python 3 patch), as R1's ORA2 gate did.
case "${RUNTIME}:${MODE}" in
    py36:installed) ATTEMPT=1 ORA2_COMMIT=d3f24a9c539528e960c8dcc9aef200cea0c49baf ORA2_SOURCE= ORA2_RUNTIME=1 ;;
    py27:installed) ATTEMPT=1 ORA2_COMMIT=4fcfa2343ab0297da30e4cc6f812ab2e2cc7da92 ORA2_SOURCE= ORA2_RUNTIME=0 ;;
    py27:source) ATTEMPT=2 ORA2_COMMIT=d3f24a9c539528e960c8dcc9aef200cea0c49baf ORA2_SOURCE=${WORKSPACE}/edx-ora2 ORA2_RUNTIME=0 ;;
    *) echo "mode must be installed, or source with py27" >&2; exit 2 ;;
esac
NS=py36-r2-e6-${RUNTIME}
LOG_ROOT=${PY36_R2_E6_LOG_ROOT:-/tmp/py36-r2-e6-20261010}/${RUNTIME}
SOURCE_ROOT=${WORKSPACE}/platform-r2-py36-src
RESPONSE_MARKER=ORA2_RESPONSE_${RUNTIME}_A${ATTEMPT}
FEEDBACK_MARKER=ORA2_FEEDBACK_${RUNTIME}_A${ATTEMPT}

mkdir -p "${OUT}/fixture-evidence"
OUT=$(CDPATH= cd -- "${OUT}" && pwd -P)
EVIDENCE=${OUT}/fixture-evidence
HANDSHAKE=${OUT}/browser/harness/out/evidence

cat > "${OUT}/script.env" <<EOF
PY36_R1_ORA2_RUNTIME=${RUNTIME}
PY36_R1_ORA2_ATTEMPT=${ATTEMPT}
PY36_R1_ORA2_USERNAME=qaora2_${RUNTIME}
PY36_R1_ORA2_EMAIL=qaora2_${RUNTIME}@example.com
PY36_R1_ORA2_STAFF_USERNAME=qaora2staff_${RUNTIME}
PY36_R1_ORA2_STAFF_EMAIL=qaora2staff_${RUNTIME}@example.com
PY36_R1_ORA2_COURSE_KEY=course-v1:QA+ORA2Assessment+${SUFFIX}
PY36_R1_ORA2_NAMESPACE=${NS}
PY36_R1_ORA2_SITE_DOMAIN=localhost:18000
PY36_R1_ORA2_RESPONSE_MARKER=${RESPONSE_MARKER}
PY36_R1_ORA2_FEEDBACK_MARKER=${FEEDBACK_MARKER}
PY36_R1_ORA2_EVIDENCE_DIR=/edx/var/r2-evidence
PY36_R1_ORA2_WORKER_LOG=/edx/var/log/worker.log
PY36_R1_ORA2_LMS_LOG=/edx/var/log/lms.log
PY36_R1_ORA2_HANDSHAKE_DIR=/edx/var/log/handshakes
PY36_R2_E6_EXPECTED_ORA2_COMMIT=${ORA2_COMMIT}
PY36_R2_E6_PLATFORM_COMMIT=$(git -C "${SOURCE_ROOT}" rev-parse HEAD)
PY36_R2_E6_PLATFORM_TREE=$(git -C "${SOURCE_ROOT}" rev-parse 'HEAD^{tree}')
EOF

fail() { echo "E6_ORA2_FAIL runtime=${RUNTIME} mode=${MODE} step=$*" >&2; exit 1; }

services() {
    PY36_R2_E6_WITH_BROKER=1 PY36_R2_E6_ORA2_SOURCE=${ORA2_SOURCE} PY36_R2_E6_ORA2_RUNTIME=${ORA2_RUNTIME} \
        PY36_R2_E6_SCRIPT_ENV_FILE="${OUT}/script.env" \
        "${SCRIPT_DIR}/run-r2-e6-services.sh" "${RUNTIME}" "$@"
}

# The E6 LMS logs to its container output; R1 redirected the same stream to
# /edx/var/log/lms.log, whose post-preflight window the provisioner scans.
refresh_lms_log() {
    docker logs "${NS}-lms" > "${LOG_ROOT}/lms/lms.log.tmp" 2>&1
    mv "${LOG_ROOT}/lms/lms.log.tmp" "${LOG_ROOT}/lms/lms.log"
}

step() {
    name=$1 action=$2 marker=$3
    refresh_lms_log
    if ! services script r2-e6-ora2.py "${EVIDENCE}" "${action}" > "${OUT}/${name}.txt" 2>&1; then
        tail -n 40 "${OUT}/${name}.txt" >&2
        return 1
    fi
    test "$(grep -c "^${marker} " "${OUT}/${name}.txt")" = 1 || return 1
    echo "${name}: ${marker}"
}

# R1's release: the request names this runtime and attempt; the release is the
# action's payload plus its status label.
release() {
    request=${HANDSHAKE}/$1 release_file=${HANDSHAKE}/$2 action=$3 label=$4 tries=0
    until [ -s "${request}" ]; do
        if ! kill -0 "${browser_pid}" 2>/dev/null; then echo "browser exited before $1" >&2; return 1; fi
        tries=$((tries + 1))
        if [ "${tries}" -ge 300 ]; then echo "no $1" >&2; return 1; fi
        sleep 1
    done
    cp "${request}" "${EVIDENCE}/"
    jq -e --arg runtime "${RUNTIME}" --arg attempt "${ATTEMPT}" \
        '.runtime == $runtime and (.attempt | tostring) == $attempt' "${request}" >/dev/null || return 1
    step "${action}" "${action}" "${label}" || return 1
    sed -n "s/^${label} //p" "${OUT}/${action}.txt" |
        jq -e --arg status "${label}" '. + {status: $status}' > "${release_file}.tmp" || return 1
    mv "${release_file}.tmp" "${release_file}"
    cp "${release_file}" "${EVIDENCE}/"
}

if ! PY36_R2_E6_PRESTART="r2-e6-ora2.py ${EVIDENCE} provision" services start > "${OUT}/stack-start.txt" 2>&1; then
    tail -n 40 "${OUT}/stack-start.txt" >&2
    fail "start/provision"
fi
cp "${LOG_ROOT}/prestart.txt" "${OUT}/provision.txt"
test "$(grep -c '^PROVISION_OK ' "${OUT}/provision.txt")" = 1 || fail provision
grep '^E6_ORA2_SITE ' "${OUT}/provision.txt" || fail "provision (site not merged)"
echo "provision: PROVISION_OK"
step identity identity IDENTITY_OK || fail identity
step preflight preflight PRECONDITION_OK || fail preflight

BROWSER_ORA2_RUNTIME=${RUNTIME}
BROWSER_ORA2_ATTEMPT=${ATTEMPT}
BROWSER_ORA2_USERNAME=qaora2_${RUNTIME}
BROWSER_ORA2_EMAIL=qaora2_${RUNTIME}@example.com
BROWSER_ORA2_STAFF_USERNAME=qaora2staff_${RUNTIME}
BROWSER_ORA2_STAFF_EMAIL=qaora2staff_${RUNTIME}@example.com
BROWSER_ORA2_COURSE_KEY=course-v1:QA+ORA2Assessment+${SUFFIX}
BROWSER_ORA2_BLOCK_ID=p1b_ora2_staff_${RUNTIME}
BROWSER_ORA2_RESPONSE_MARKER=${RESPONSE_MARKER}
BROWSER_ORA2_FEEDBACK_MARKER=${FEEDBACK_MARKER}
BROWSER_ACCEPTANCE_BASE_URL=http://localhost:18000
BROWSER_ORA2_EVIDENCE_DIR=/work/out/evidence
BROWSER_ORA2_STATE_FILE=/work/out/evidence/state.json
BROWSER_ORA2_SUBMISSION_REQUEST=/work/out/evidence/submission-request.json
BROWSER_ORA2_SUBMISSION_RELEASE=/work/out/evidence/submission-release.json
BROWSER_ORA2_LEASE_REQUEST=/work/out/evidence/lease-request.json
BROWSER_ORA2_LEASE_RELEASE=/work/out/evidence/lease-release.json
BROWSER_ORA2_POST_REQUEST=/work/out/evidence/postcondition-request.json
BROWSER_ORA2_POST_RELEASE=/work/out/evidence/postcondition-release.json
export BROWSER_ORA2_RUNTIME BROWSER_ORA2_ATTEMPT BROWSER_ORA2_USERNAME BROWSER_ORA2_EMAIL \
    BROWSER_ORA2_STAFF_USERNAME BROWSER_ORA2_STAFF_EMAIL BROWSER_ORA2_COURSE_KEY BROWSER_ORA2_BLOCK_ID \
    BROWSER_ORA2_RESPONSE_MARKER BROWSER_ORA2_FEEDBACK_MARKER BROWSER_ACCEPTANCE_BASE_URL \
    BROWSER_ORA2_EVIDENCE_DIR BROWSER_ORA2_STATE_FILE \
    BROWSER_ORA2_SUBMISSION_REQUEST BROWSER_ORA2_SUBMISSION_RELEASE \
    BROWSER_ORA2_LEASE_REQUEST BROWSER_ORA2_LEASE_RELEASE BROWSER_ORA2_POST_REQUEST BROWSER_ORA2_POST_RELEASE
E6_SPEC=tests/ora2_assessment.spec.ts E6_TEST_TIMEOUT_MS=${E6_TEST_TIMEOUT_MS:-300000} \
    "${SCRIPT_DIR}/r2-e6-browser.sh" "${RUNTIME}" "${OUT}/browser" > "${OUT}/browser.txt" 2>&1 &
browser_pid=$!

handshake_rc=0
release submission-request.json submission-release.json submission-ready SUBMISSION_READY_OK || handshake_rc=1
if [ "${handshake_rc}" -eq 0 ]; then
    release lease-request.json lease-release.json staff-lease STAFF_LEASE_OK || handshake_rc=2
fi
if [ "${handshake_rc}" -eq 0 ]; then
    release postcondition-request.json postcondition-release.json postflight POSTCONDITION_OK || handshake_rc=3
fi
if [ "${handshake_rc}" -ne 0 ]; then
    kill "${browser_pid}" 2>/dev/null || true
    wait "${browser_pid}" 2>/dev/null || true
    # Killing the launcher leaves its `docker run --rm` Chromium container running.
    for c in $(docker ps -q --filter label=io.openedx.py36-r2.gate=e6-browser); do docker rm -f "$c" >/dev/null; done
    tail -n 30 "${OUT}/browser.txt" >&2
    fail "handshake ${handshake_rc}"
fi

browser_rc=0
wait "${browser_pid}" || browser_rc=$?
cat "${OUT}/browser.txt"
STATE=${OUT}/browser/evidence/state.json
test -f "${STATE}" || fail "browser rc=${browser_rc} (no state file)"
jq -e --arg runtime "${RUNTIME}" --arg attempt "${ATTEMPT}" \
    '.status == "BROWSER_ORA2_OK" and .runtime == $runtime and (.attempt | tostring) == $attempt' \
    "${STATE}" >/dev/null || fail "browser state"
if [ "${browser_rc}" -ne 0 ]; then fail "browser rc=${browser_rc}"; fi
refresh_lms_log
echo "E6_ORA2_OK runtime=${RUNTIME} mode=${MODE} attempt=${ATTEMPT} ora2=${ORA2_COMMIT}"
