#!/bin/sh
# R2-preview E6 Studio edit/publish gate. Starts the runtime's default E6 stack
# (eager Celery, no forum or broker) with the R1 provisioner as its prestart
# step, then reset/preflight -> Chromium: author saves a draft in Studio ->
# external midcondition -> learner sees the baseline -> author publishes ->
# external postflight -> learner hard-refresh sees the edit. The spec's
# external calls arrive through /work/e6/handshake.sh and are answered here.
# usage: r2-e6-studio.sh {py36|py27} <out-dir>
#   Leaves the stack running; remove it with run-r2-e6-services.sh <rt> cleanup.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
RUNTIME=$1; OUT=$2; ATTEMPT=1
case "${RUNTIME}" in py36|py27) ;; *) echo "runtime must be py36 or py27" >&2; exit 2 ;; esac
case "${RUNTIME}" in py36) SUFFIX=Py36 ;; py27) SUFFIX=Py27 ;; esac
UPPER=$(printf '%s' "${RUNTIME}" | tr '[:lower:]' '[:upper:]')
NS=py36-r2-e6-${RUNTIME}
SECRETS=/Users/noahwang/workspace/hawthorn/.py36-r2-config/e6-studio.env
LOG_ROOT=${PY36_R2_E6_LOG_ROOT:-/tmp/py36-r2-e6-20261010}/${RUNTIME}

mkdir -p "${OUT}/fixture-evidence"
OUT=$(CDPATH= cd -- "${OUT}" && pwd -P)
EVIDENCE=${OUT}/fixture-evidence
HANDSHAKE=${OUT}/browser/harness/out/handshake

if [ ! -f "${SECRETS}" ]; then
    (umask 077
     printf 'PY36_R1_STUDIO_AUTHOR_PASSWORD=%s\nPY36_R1_STUDIO_LEARNER_PASSWORD=%s\n' \
        "$(openssl rand -hex 16)" "$(openssl rand -hex 16)" > "${SECRETS}")
fi

cat > "${OUT}/script.env" <<EOF
PY36_R1_STUDIO_RUNTIME=${RUNTIME}
PY36_R1_STUDIO_ATTEMPT=${ATTEMPT}
PY36_R1_STUDIO_AUTHOR=qastudio_${RUNTIME}
PY36_R1_STUDIO_LEARNER=qastudiolearner_${RUNTIME}
PY36_R1_STUDIO_COURSE_KEY=course-v1:QA+StudioPublish+${SUFFIX}
PY36_R1_STUDIO_NAMESPACE=${NS}
PY36_R1_STUDIO_EVIDENCE_DIR=/edx/var/r2-evidence
EOF

fail() { echo "E6_STUDIO_FAIL runtime=${RUNTIME} step=$*" >&2; exit 1; }

services() {
    PY36_R2_E6_SCRIPT_SERVICE=cms PY36_R2_E6_SCRIPT_ENV_FILE="${OUT}/script.env ${SECRETS}" \
        "${SCRIPT_DIR}/run-r2-e6-services.sh" "${RUNTIME}" "$@"
}

step() {
    name=$1 action=$2 marker=$3
    if ! services script r2-e6-studio.py "${EVIDENCE}" "${action}" > "${OUT}/${name}.log" 2>&1; then
        tail -n 40 "${OUT}/${name}.log" >&2
        return 1
    fi
    grep -q "^${marker} " "${OUT}/${name}.log" || return 1
    echo "${name}: ${marker}"
}

if ! PY36_R2_E6_PRESTART="r2-e6-studio.py ${EVIDENCE} provision" services start > "${OUT}/stack-start.txt" 2>&1; then
    tail -n 40 "${OUT}/stack-start.txt" >&2
    fail "start/provision"
fi
cp "${LOG_ROOT}/prestart.txt" "${OUT}/provision.log"
grep -q '^PROVISION_OK ' "${OUT}/provision.log" || fail provision
grep '^E6_STUDIO_SITE ' "${OUT}/provision.log"
echo "provision: PROVISION_OK"
step reset reset STUDIO_RESET_OK || fail reset
step preflight preflight STUDIO_PREFLIGHT_OK || fail preflight

BROWSER_STUDIO_RUNTIME=${RUNTIME}
BROWSER_STUDIO_ATTEMPT=${ATTEMPT}
BROWSER_STUDIO_CMS_BASE_URL=http://localhost:18010
BROWSER_STUDIO_LMS_BASE_URL=http://localhost:18000
BROWSER_ACCEPTANCE_BASE_URL=http://localhost:18000
BROWSER_STUDIO_COURSE_KEY=course-v1:QA+StudioPublish+${SUFFIX}
BROWSER_STUDIO_AUTHOR_EMAIL=qastudio_${RUNTIME}@example.com
BROWSER_STUDIO_LEARNER_EMAIL=qastudiolearner_${RUNTIME}@example.com
BROWSER_STUDIO_AUTHOR_PASSWORD=$(sed -n 's/^PY36_R1_STUDIO_AUTHOR_PASSWORD=//p' "${SECRETS}")
BROWSER_STUDIO_LEARNER_PASSWORD=$(sed -n 's/^PY36_R1_STUDIO_LEARNER_PASSWORD=//p' "${SECRETS}")
BROWSER_STUDIO_SERVICE_SCRIPT=/work/e6/handshake.sh
BROWSER_STUDIO_EVIDENCE_DIR=/work/out/evidence
BROWSER_STUDIO_BASELINE=STUDIO_PUBLISH_BASELINE_${UPPER}
BROWSER_STUDIO_MARKER=STUDIO_PUBLISH_AFTER_${UPPER}_ATTEMPT_${ATTEMPT}
export BROWSER_STUDIO_RUNTIME BROWSER_STUDIO_ATTEMPT BROWSER_STUDIO_CMS_BASE_URL BROWSER_STUDIO_LMS_BASE_URL \
    BROWSER_ACCEPTANCE_BASE_URL BROWSER_STUDIO_COURSE_KEY BROWSER_STUDIO_AUTHOR_EMAIL \
    BROWSER_STUDIO_LEARNER_EMAIL BROWSER_STUDIO_AUTHOR_PASSWORD BROWSER_STUDIO_LEARNER_PASSWORD \
    BROWSER_STUDIO_SERVICE_SCRIPT BROWSER_STUDIO_EVIDENCE_DIR BROWSER_STUDIO_BASELINE BROWSER_STUDIO_MARKER
E6_SPEC=tests/studio_edit_publish.spec.ts E6_TEST_TIMEOUT_MS=${E6_TEST_TIMEOUT_MS:-300000} \
    "${SCRIPT_DIR}/r2-e6-browser.sh" "${RUNTIME}" "${OUT}/browser" > "${OUT}/browser.log" 2>&1 &
browser_pid=$!

# The spec gives each external call 120 s.
answer() {
    request=$1
    id=$(basename "${request}" .request)
    set -- $(cat "${request}")
    case "$2" in
        midcondition) marker=MIDCONDITION_OK ;;
        postflight) marker=STUDIO_POSTFLIGHT_OK ;;
        *) printf 'unsupported action %s\n' "$2" > "${HANDSHAKE}/${id}.out"; echo 2 > "${HANDSHAKE}/${id}.rc"; return ;;
    esac
    if [ "$1" != "${RUNTIME}" ] || [ "$3" != "${ATTEMPT}" ]; then
        printf 'unexpected request %s\n' "$*" > "${HANDSHAKE}/${id}.out"; echo 2 > "${HANDSHAKE}/${id}.rc"; return
    fi
    rc=0
    step "$2" "$2" "${marker}" || rc=1
    cp "${OUT}/$2.log" "${HANDSHAKE}/${id}.out"
    echo "${rc}" > "${HANDSHAKE}/${id}.rc.tmp"
    mv "${HANDSHAKE}/${id}.rc.tmp" "${HANDSHAKE}/${id}.rc"
}

while kill -0 "${browser_pid}" 2>/dev/null; do
    for request in "${HANDSHAKE}"/*.request; do
        [ -f "${request}" ] || continue
        [ -f "${request%.request}.rc" ] && continue
        answer "${request}"
    done
    sleep 1
done
browser_rc=0
wait "${browser_pid}" || browser_rc=$?
grep -v '^npm notice' "${OUT}/browser.log" | grep -v '^BROWSER_STUDIO_EDIT_PUBLISH_OK ' || true
for name in midcondition postflight; do
    test -f "${OUT}/${name}.log" || fail "browser rc=${browser_rc} (no ${name} request)"
done
if [ "${browser_rc}" -ne 0 ]; then fail "browser rc=${browser_rc}"; fi
test -f "${OUT}/browser/evidence/${RUNTIME}-attempt${ATTEMPT}-browser.json" || fail "browser (no evidence json)"
echo "E6_STUDIO_OK runtime=${RUNTIME} attempt=${ATTEMPT}"
