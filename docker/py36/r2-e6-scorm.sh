#!/bin/sh
# R2-preview E6 SCORM render gate. Starts the runtime's E6 stack with the R1
# provisioner as its prestart step (published SCORM 1.2 course, package in the
# stack's DJFS root), then identity -> preflight -> Chromium: the enrolled
# learner opens the unit, the package renders in its iframe and initializes
# the SCORM API -> postflight (render-only state).
# usage: r2-e6-scorm.sh {py36|py27} <out-dir> [installed|source]
#   installed (default): the image's scormxblock. source (py27 only): the
#   read-only 8a6c07d5 checkout (R2 requirements pin) through
#   PY36_R2_E6_SCORM_SOURCE; runs as attempt 2 so its evidence differs.
#   Leaves the stack running; remove it with run-r2-e6-services.sh <rt> cleanup.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
WORKSPACE=/Users/noahwang/workspace/hawthorn
RUNTIME=$1; OUT=$2; MODE=${3:-installed}
case "${RUNTIME}" in py36|py27) ;; *) echo "runtime must be py36 or py27" >&2; exit 2 ;; esac
case "${RUNTIME}" in py36) SUFFIX=Py36 ;; py27) SUFFIX=Py27 ;; esac
R2_PIN=8a6c07d562217500fa8236f555343c9921ef4907
case "${RUNTIME}:${MODE}" in
    py36:installed|py27:source)
        SCORM_COMMIT=${R2_PIN} SCORM_TREE=595e291da2d3a7983a290fdc433e1471805b2525
        SCORM_MODULE_SHA256=0b3b9304ecf20fb63009e8ba0b33857bbea3e868c25d9f087fb55d91438511b6 ;;
    # The Python 2.7 runner's editable scormxblock is the workspace src checkout
    # (master's @hawthorn pin), the parent of the R2 pin.
    py27:installed)
        SCORM_COMMIT=841e1630bf468c724ca0690f619569342afc70de SCORM_TREE=5f3c9d8ffcb71102c50ee0def6d2f923e8de0964
        SCORM_MODULE_SHA256=6e4e90759316c31afe67880d1cab7858b40e3f57e7a0cdf3bda31fbb30103ecb ;;
    *) echo "mode must be installed, or source with py27" >&2; exit 2 ;;
esac
case "${MODE}" in
    installed) ATTEMPT=1 SCORM_SOURCE= SCORM_SOURCE_ROOT= ;;
    source) ATTEMPT=2 SCORM_SOURCE=${WORKSPACE}/.py36-r2-sources/edx_xblock_scorm-${R2_PIN} SCORM_SOURCE_ROOT=/runner/scormxblock ;;
esac
NS=py36-r2-e6-${RUNTIME}
LOG_ROOT=${PY36_R2_E6_LOG_ROOT:-/tmp/py36-r2-e6-20261010}/${RUNTIME}
SOURCE_ROOT=${WORKSPACE}/platform-r2-py36-src
USERNAME=qascorm_${RUNTIME}
EMAIL=qascorm_${RUNTIME}@example.com
COURSE_KEY=course-v1:QA+SCORMRender+${SUFFIX}

mkdir -p "${OUT}/fixture-evidence"
OUT=$(CDPATH= cd -- "${OUT}" && pwd -P)
EVIDENCE=${OUT}/fixture-evidence

cat > "${OUT}/script.env" <<EOF
PY36_R1_SCORM_RUNTIME=${RUNTIME}
PY36_R1_SCORM_ATTEMPT=${ATTEMPT}
PY36_R1_SCORM_USERNAME=${USERNAME}
PY36_R1_SCORM_EMAIL=${EMAIL}
PY36_R1_SCORM_COURSE_KEY=${COURSE_KEY}
PY36_R1_SCORM_NAMESPACE=${NS}
PY36_R1_SCORM_SITE_DOMAIN=localhost:18000
PY36_R1_SCORM_PLATFORM_COMMIT=$(git -C "${SOURCE_ROOT}" rev-parse HEAD)
PY36_R1_SCORM_PLATFORM_TREE=$(git -C "${SOURCE_ROOT}" rev-parse 'HEAD^{tree}')
PY36_R2_E6_SCORM_COMMIT=${SCORM_COMMIT}
PY36_R2_E6_SCORM_TREE=${SCORM_TREE}
PY36_R2_E6_SCORM_MODULE_SHA256=${SCORM_MODULE_SHA256}
PY36_R2_E6_SCORM_SOURCE_ROOT=${SCORM_SOURCE_ROOT}
EOF

fail() { echo "E6_SCORM_FAIL runtime=${RUNTIME} mode=${MODE} step=$*" >&2; exit 1; }

services() {
    PY36_R2_E6_SCORM_SOURCE=${SCORM_SOURCE} PY36_R2_E6_SCRIPT_ENV_FILE="${OUT}/script.env" \
        "${SCRIPT_DIR}/run-r2-e6-services.sh" "${RUNTIME}" "$@"
}

step() {
    name=$1 marker=$2
    if ! services script r2-e6-scorm.py "${EVIDENCE}" "${name}" > "${OUT}/${name}.txt" 2>&1; then
        tail -n 40 "${OUT}/${name}.txt" >&2
        return 1
    fi
    test "$(grep -c "^${marker} " "${OUT}/${name}.txt")" = 1 || return 1
    echo "${name}: ${marker}"
}

if ! PY36_R2_E6_PRESTART="r2-e6-scorm.py ${EVIDENCE} provision" services start > "${OUT}/stack-start.txt" 2>&1; then
    tail -n 40 "${OUT}/stack-start.txt" >&2
    fail "start/provision"
fi
cp "${LOG_ROOT}/prestart.txt" "${OUT}/provision.txt"
test "$(grep -c '^PROVISION_OK ' "${OUT}/provision.txt")" = 1 || fail provision
grep '^E6_SCORM_SITE ' "${OUT}/provision.txt" || fail "provision (site not unthemed)"
echo "provision: PROVISION_OK"
step identity IDENTITY_OK || fail identity
step preflight PRECONDITION_OK || fail preflight

BROWSER_SCORM_RUNTIME=${RUNTIME}
BROWSER_SCORM_ATTEMPT=${ATTEMPT}
BROWSER_SCORM_USERNAME=${USERNAME}
BROWSER_SCORM_EMAIL=${EMAIL}
BROWSER_SCORM_COURSE_KEY=${COURSE_KEY}
BROWSER_SCORM_EVIDENCE_DIR=/work/out/evidence
BROWSER_SCORM_STATE_FILE=/work/out/evidence/state.json
BROWSER_ACCEPTANCE_BASE_URL=http://localhost:18000
export BROWSER_SCORM_RUNTIME BROWSER_SCORM_ATTEMPT BROWSER_SCORM_USERNAME BROWSER_SCORM_EMAIL \
    BROWSER_SCORM_COURSE_KEY BROWSER_SCORM_EVIDENCE_DIR BROWSER_SCORM_STATE_FILE BROWSER_ACCEPTANCE_BASE_URL
browser_rc=0
E6_SPEC=tests/scorm_render.spec.ts E6_TEST_TIMEOUT_MS=${E6_TEST_TIMEOUT_MS:-120000} \
    "${SCRIPT_DIR}/r2-e6-browser.sh" "${RUNTIME}" "${OUT}/browser" > "${OUT}/browser.txt" 2>&1 || browser_rc=$?
cat "${OUT}/browser.txt"
STATE=${OUT}/browser/evidence/state.json
test -f "${STATE}" || fail "browser rc=${browser_rc} (no state file)"
jq -e --arg runtime "${RUNTIME}" --arg attempt "${ATTEMPT}" \
    '.status == "BROWSER_SCORM_OK" and .runtime == $runtime and (.attempt | tostring) == $attempt' \
    "${STATE}" >/dev/null || fail "browser state"
if [ "${browser_rc}" -ne 0 ]; then fail "browser rc=${browser_rc}"; fi
step postflight POSTCONDITION_OK || fail postflight
echo "E6_SCORM_OK runtime=${RUNTIME} mode=${MODE} attempt=${ATTEMPT} scorm=${SCORM_COMMIT}"
