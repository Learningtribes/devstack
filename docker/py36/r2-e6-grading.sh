#!/bin/sh
# R2-preview E6 grading mutation gate on a stack started with
# PY36_R2_E6_WITH_BROKER=1: provision -> reset/preflight -> Chromium wrong
# answer -> midcondition (asynchronous grade/progress tasks done on the stack's
# own worker) -> Chromium correct answer -> postflight.
# usage: r2-e6-grading.sh {py36|py27} <out-dir>
#   One run per fresh stack: the provisioner counts tasks across the worker's
#   whole log, so the attempt is always 1.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
RUNTIME=$1; OUT=$2; ATTEMPT=1
case "${RUNTIME}" in py36|py27) ;; *) echo "runtime must be py36 or py27" >&2; exit 2 ;; esac
NS=py36-r2-e6-${RUNTIME}
for c in rabbitmq worker lms; do test "$(docker inspect "${NS}-${c}" --format '{{.State.Running}}')" = true; done
WORKER_LOG=${PY36_R2_E6_LOG_ROOT:-/tmp/py36-r2-e6-20261010}/${RUNTIME}/lms/worker.log

mkdir -p "${OUT}/fixture-evidence"
OUT=$(CDPATH= cd -- "${OUT}" && pwd -P)
EVIDENCE=${OUT}/fixture-evidence
HANDSHAKE=${OUT}/browser/harness/out/evidence
case "${RUNTIME}" in py36) COURSE_SUFFIX=Py36 ;; py27) COURSE_SUFFIX=Py27 ;; esac

cat > "${OUT}/script.env" <<EOF
PY36_R1_GRADING_RUNTIME=${RUNTIME}
PY36_R1_GRADING_ATTEMPT=${ATTEMPT}
PY36_R1_GRADING_USERNAME=qagrade_${RUNTIME}
PY36_R1_GRADING_EMAIL=qagrade_${RUNTIME}@example.com
PY36_R1_GRADING_COURSE_KEY=course-v1:QA+GradingMutation+${COURSE_SUFFIX}
PY36_R1_GRADING_NAMESPACE=${NS}
PY36_R1_GRADING_SITE_DOMAIN=localhost:18000
PY36_R1_GRADING_EVIDENCE_DIR=/edx/var/r2-evidence
PY36_R1_GRADING_WORKER_LOG=/edx/var/log/worker.log
EOF

fail() { echo "E6_GRADING_FAIL runtime=${RUNTIME} step=$*" >&2; exit 1; }

step() {
    name=$1 action=$2 marker=$3
    if ! PY36_R2_E6_SCRIPT_ENV_FILE=${OUT}/script.env "${SCRIPT_DIR}/run-r2-e6-services.sh" "${RUNTIME}" \
        script r2-e6-grading.py "${EVIDENCE}" "${action}" > "${OUT}/${name}.log" 2>&1; then
        tail -n 40 "${OUT}/${name}.log" >&2
        return 1
    fi
    grep -q "^${marker} " "${OUT}/${name}.log" || return 1
    echo "${name}: ${marker}"
}

succeeded() { grep -c -E "Task [a-z_.]*\\.$1\\[[0-9a-f-]+\\] succeeded" "${WORKER_LOG}" || true; }

wait_for_tasks() {
    grade=$1 progress=$2 tries=0
    until [ "$(succeeded recalculate_subsection_grade_v3)" -ge "${grade}" ] &&
          [ "$(succeeded calculate_course_progress)" -ge "${progress}" ]; do
        tries=$((tries + 1))
        if [ "${tries}" -ge 60 ]; then return 1; fi
        sleep 1
    done
}

step provision provision PROVISION_OK || fail provision
grep '^E6_GRADING_UNTHEMED ' "${OUT}/provision.log" || fail "provision (site theme not removed)"
step preflight reset RESET_OK || fail preflight

BROWSER_GRADING_RUNTIME=${RUNTIME}
BROWSER_GRADING_ATTEMPT=${ATTEMPT}
BROWSER_GRADING_USERNAME=qagrade_${RUNTIME}
BROWSER_GRADING_EMAIL=qagrade_${RUNTIME}@example.com
BROWSER_GRADING_COURSE_KEY=course-v1:QA+GradingMutation+${COURSE_SUFFIX}
BROWSER_GRADING_PROBLEM_ID=p1b_grading_problem_${RUNTIME}
BROWSER_ACCEPTANCE_BASE_URL=http://localhost:18000
BROWSER_GRADING_EVIDENCE_DIR=/work/out/evidence
BROWSER_GRADING_STATE_FILE=/work/out/evidence/state.json
BROWSER_GRADING_MIDCONDITION_REQUEST=/work/out/evidence/midcondition.request
BROWSER_GRADING_MIDCONDITION_RELEASE=/work/out/evidence/midcondition.release
export BROWSER_GRADING_RUNTIME BROWSER_GRADING_ATTEMPT BROWSER_GRADING_USERNAME BROWSER_GRADING_EMAIL \
    BROWSER_GRADING_COURSE_KEY BROWSER_GRADING_PROBLEM_ID BROWSER_ACCEPTANCE_BASE_URL \
    BROWSER_GRADING_EVIDENCE_DIR BROWSER_GRADING_STATE_FILE BROWSER_GRADING_MIDCONDITION_REQUEST \
    BROWSER_GRADING_MIDCONDITION_RELEASE
E6_SPEC=tests/grading_mutation.spec.ts E6_TEST_TIMEOUT_MS=${E6_TEST_TIMEOUT_MS:-180000} \
    "${SCRIPT_DIR}/r2-e6-browser.sh" "${RUNTIME}" "${OUT}/browser" > "${OUT}/browser.log" 2>&1 &
browser_pid=$!

# The spec waits 120 s for the release after writing the request.
tries=0
until [ -f "${HANDSHAKE}/midcondition.request" ]; do
    if ! kill -0 "${browser_pid}" 2>/dev/null; then
        wait "${browser_pid}" || true
        tail -n 20 "${OUT}/browser.log" >&2
        fail "browser (exited before the midcondition request)"
    fi
    tries=$((tries + 1))
    if [ "${tries}" -ge 300 ]; then kill "${browser_pid}" 2>/dev/null || true; fail "browser (no midcondition request)"; fi
    sleep 1
done
cp "${HANDSHAKE}/midcondition.request" "${EVIDENCE}/midcondition.request"
mid_rc=0
wait_for_tasks 1 1 || mid_rc=$?
if [ "${mid_rc}" -eq 0 ]; then step midcondition midcondition MIDCONDITION_OK || mid_rc=$?; fi
if [ "${mid_rc}" -ne 0 ]; then
    kill "${browser_pid}" 2>/dev/null || true
    wait "${browser_pid}" 2>/dev/null || true
    fail midcondition
fi
cp "${EVIDENCE}/midcondition.release" "${HANDSHAKE}/midcondition.release"

browser_rc=0
wait "${browser_pid}" || browser_rc=$?
cat "${OUT}/browser.log"
if [ ! -f "${OUT}/browser/evidence/state.json" ]; then fail "browser rc=${browser_rc} (no state file)"; fi
wait_for_tasks 2 1 || fail "postflight (grade tasks not finished)"
step postflight postflight POSTCONDITION_OK || fail postflight
if [ "${browser_rc}" -ne 0 ]; then fail "browser rc=${browser_rc}"; fi
echo "E6_GRADING_OK runtime=${RUNTIME} attempt=${ATTEMPT}"
