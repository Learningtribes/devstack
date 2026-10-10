#!/bin/sh
# R2-preview E6 discussion read/write gate on a stack started with
# PY36_R2_E6_WITH_FORUM=1: provision -> reset/preflight -> Chromium
# create/read/reply/refresh -> postflight, all against the stack's private
# comments service, Mongo and Elasticsearch.
# usage: r2-e6-discussion.sh {py36|py27} <out-dir> [attempt] [previous-state.json]
#   previous-state.json is the browser state of an earlier attempt; reset
#   deletes exactly the thread and comment it names before preflight.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
RUNTIME=$1; OUT=$2; ATTEMPT=${3:-1}; PREVIOUS_STATE=${4:-}
case "${RUNTIME}" in py36|py27) ;; *) echo "runtime must be py36 or py27" >&2; exit 2 ;; esac
NS=py36-r2-e6-${RUNTIME}
test "$(docker inspect "${NS}-forum" --format '{{.State.Running}}')" = true
test "$(docker inspect "${NS}-lms" --format '{{.State.Running}}')" = true

mkdir -p "${OUT}/fixture-evidence"
OUT=$(CDPATH= cd -- "${OUT}" && pwd -P)
EVIDENCE=${OUT}/fixture-evidence
case "${RUNTIME}" in py36) COURSE_SUFFIX=Py36 ;; py27) COURSE_SUFFIX=Py27 ;; esac

cat > "${OUT}/script.env" <<EOF
PY36_R1_DISCUSSION_RUNTIME=${RUNTIME}
PY36_R1_DISCUSSION_ATTEMPT=${ATTEMPT}
PY36_R1_DISCUSSION_MONGO_URI=mongodb://${NS}-mongo:27017/cs_comments_service
PY36_R1_DISCUSSION_SEARCH_SERVER=http://${NS}-es:9200
PY36_R1_DISCUSSION_EVIDENCE_DIR=/edx/var/r2-evidence
EOF
if [ -n "${PREVIOUS_STATE}" ]; then
    cp "${PREVIOUS_STATE}" "${EVIDENCE}/previous-state.json"
    cp "${OUT}/script.env" "${OUT}/reset.env"
    echo "PY36_R1_DISCUSSION_STATE_FILE=/edx/var/r2-evidence/previous-state.json" >> "${OUT}/reset.env"
else
    cp "${OUT}/script.env" "${OUT}/reset.env"
fi

step() {
    name=$1 env_file=$2 action=$3 marker=$4
    if ! PY36_R2_E6_SCRIPT_ENV_FILE=${env_file} "${SCRIPT_DIR}/run-r2-e6-services.sh" "${RUNTIME}" \
        script r2-e6-discussion.py "${EVIDENCE}" "${action}" > "${OUT}/${name}.log" 2>&1; then
        tail -n 40 "${OUT}/${name}.log" >&2
        echo "E6_DISCUSSION_FAIL runtime=${RUNTIME} step=${name}" >&2
        exit 1
    fi
    grep -q "^${marker} " "${OUT}/${name}.log"
    echo "${name}: ${marker}"
}

step provision "${OUT}/script.env" provision PROVISION_OK
step preflight "${OUT}/reset.env" reset PRECONDITION_OK

BROWSER_DISCUSSION_RUNTIME=${RUNTIME}
BROWSER_DISCUSSION_ATTEMPT=${ATTEMPT}
BROWSER_DISCUSSION_USERNAME=qadiscuss_${RUNTIME}
BROWSER_DISCUSSION_EMAIL=qadiscuss_${RUNTIME}@example.com
BROWSER_DISCUSSION_COURSE_KEY=course-v1:QA+DiscussionRW+${COURSE_SUFFIX}
BROWSER_DISCUSSION_ID=p1b_discussion_rw_${RUNTIME}
BROWSER_DISCUSSION_BASE_URL=http://localhost:18000
BROWSER_ACCEPTANCE_BASE_URL=http://localhost:18000
BROWSER_DISCUSSION_EVIDENCE_DIR=/work/out/evidence
BROWSER_DISCUSSION_STATE_FILE=/work/out/evidence/state.json
export BROWSER_DISCUSSION_RUNTIME BROWSER_DISCUSSION_ATTEMPT BROWSER_DISCUSSION_USERNAME \
    BROWSER_DISCUSSION_EMAIL BROWSER_DISCUSSION_COURSE_KEY BROWSER_DISCUSSION_ID \
    BROWSER_DISCUSSION_BASE_URL BROWSER_ACCEPTANCE_BASE_URL BROWSER_DISCUSSION_EVIDENCE_DIR \
    BROWSER_DISCUSSION_STATE_FILE
browser_rc=0
E6_SPEC=tests/discussion_read_write.spec.ts E6_TEST_TIMEOUT_MS=${E6_TEST_TIMEOUT_MS:-180000} \
    "${SCRIPT_DIR}/r2-e6-browser.sh" "${RUNTIME}" "${OUT}/browser" || browser_rc=$?
if [ ! -f "${OUT}/browser/evidence/state.json" ]; then
    echo "E6_DISCUSSION_FAIL runtime=${RUNTIME} step=browser rc=${browser_rc} (no state file)" >&2
    exit 1
fi
cp "${OUT}/browser/evidence/state.json" "${EVIDENCE}/browser-state.json"
cp "${OUT}/script.env" "${OUT}/postflight.env"
echo "PY36_R1_DISCUSSION_STATE_FILE=/edx/var/r2-evidence/browser-state.json" >> "${OUT}/postflight.env"
step postflight "${OUT}/postflight.env" postflight POSTCONDITION_OK

if [ "${browser_rc}" -ne 0 ]; then
    echo "E6_DISCUSSION_FAIL runtime=${RUNTIME} step=browser rc=${browser_rc}" >&2
    exit 1
fi
echo "E6_DISCUSSION_OK runtime=${RUNTIME} attempt=${ATTEMPT}"
