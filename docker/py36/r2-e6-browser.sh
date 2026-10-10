#!/bin/sh
# R2-preview E6: run harness checklists in Chromium inside the network
# namespace of an E6 stack, so localhost:18000/18010 are that runtime's LMS and
# Studio for both page loads and Playwright API requests.
# usage: r2-e6-browser.sh {py36|py27} <out-dir> <checklist.yml>...
#   A bare name is read from the harness checklists/ (must be committed and
#   unmodified); a path is used as-is.
#   E6_SPEC selects another harness spec (default tests/checklist.spec.ts);
#   BROWSER_* variables are passed through to it, and anything the spec writes
#   under /work/out/evidence is kept as <out-dir>/evidence.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
HARNESS_REPO=/Users/noahwang/workspace/hawthorn/platform-browser-acceptance-harness
HARNESS=${HARNESS_REPO}/.claude/skills/browser-acceptance
PLAYWRIGHT_IMAGE=mcr.microsoft.com/playwright@sha256:5b8f294aff9041b7191c34a4bab3ac270157a28774d4b0660e9743297b697e48
# Per-test budget; local runserver stacks (Py2.7 under amd64 emulation) can
# need more than the harness default for multi-page follow surfaces.
TEST_TIMEOUT_MS=${E6_TEST_TIMEOUT_MS:-30000}
SPEC=${E6_SPEC:-tests/checklist.spec.ts}
BROWSER_ENV_NAMES=$(env | sed -n 's/^\(BROWSER_[A-Z0-9_]*\)=.*/\1/p' | sort)

RUNTIME=$1; OUT=$2; shift 2
case "${RUNTIME}" in py36|py27) ;; *) echo "runtime must be py36 or py27" >&2; exit 2 ;; esac
NETNS=py36-r2-e6-${RUNTIME}-lms
test "$(docker inspect "${NETNS}" --format '{{.State.Running}}')" = true
test "$(docker inspect "${NETNS}" --format '{{index .Config.Labels "io.openedx.py36-r2.gate"}}')" = e6

mkdir -p "${OUT}"
OUT=$(CDPATH= cd -- "${OUT}" && pwd -P)
WORK=${OUT}/harness
rm -rf "${WORK}"
mkdir -p "${WORK}/checklists" "${WORK}/node_modules" "${WORK}/out"
cp -R "${HARNESS}/lib" "${HARNESS}/tests" "${HARNESS}/playwright.config.ts" "${HARNESS}/package.json" "${WORK}/"
test -f "${WORK}/${SPEC}"

{
    echo "runtime=${RUNTIME} netns=${NETNS} image=$(docker inspect "${NETNS}" --format '{{.Image}}')"
    echo "harness_head=$(git -C "${HARNESS_REPO}" rev-parse HEAD)"
    echo "harness_code_clean=$(git -C "${HARNESS_REPO}" status --porcelain -- .claude/skills/browser-acceptance/lib .claude/skills/browser-acceptance/tests .claude/skills/browser-acceptance/playwright.config.ts | wc -l | tr -d ' ')_changes"
    echo "playwright_image=${PLAYWRIGHT_IMAGE}"
    echo "playwright_test=$(node -p "require('${HARNESS}/node_modules/@playwright/test/package.json').version")"
    echo "test_timeout_ms=${TEST_TIMEOUT_MS}"
    echo "spec=${SPEC} sha256=$(shasum -a 256 "${WORK}/${SPEC}" | cut -d' ' -f1)"
    for name in ${BROWSER_ENV_NAMES}; do
        eval "echo \"env ${name}=\${${name}}\""
    done
    for item in "$@"; do
        case "${item}" in
            */*) src=${item} ;;
            *)
                src=${HARNESS}/checklists/${item}
                rel=.claude/skills/browser-acceptance/checklists/${item}
                git -C "${HARNESS_REPO}" ls-files --error-unmatch "${rel}" >/dev/null
                if [ -n "$(git -C "${HARNESS_REPO}" status --porcelain -- "${rel}")" ]; then
                    echo "refusing uncommitted checklist: ${rel}" >&2; exit 2
                fi
                ;;
        esac
        cp "${src}" "${WORK}/checklists/"
        echo "checklist=$(basename "${src}") sha256=$(shasum -a 256 "${src}" | cut -d' ' -f1)"
    done
    echo "started=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "${OUT}/browser-identity.txt"

env_args=
for name in ${BROWSER_ENV_NAMES}; do env_args="${env_args} --env ${name}"; done
set +e
# shellcheck disable=SC2086
docker run --rm --network "container:${NETNS}" --shm-size=1g --memory "${PY36_R2_GATE_BROWSER_MEMORY:-3g}" \
    --label io.openedx.py36-r2.gate=e6-browser \
    --mount "type=bind,src=${WORK},dst=/work" \
    --mount "type=bind,src=${HARNESS}/node_modules,dst=/work/node_modules,readonly" \
    --env PLAYWRIGHT_JSON_OUTPUT_NAME=/work/out/results.json ${env_args} \
    -w /work "${PLAYWRIGHT_IMAGE}" \
    npx playwright test "${SPEC}" --reporter=list,json --retries=0 --timeout="${TEST_TIMEOUT_MS}" \
        --trace=retain-on-failure --output=/work/out/test-results \
    > "${OUT}/playwright.txt" 2>&1
rc=$?
set -e
echo "finished=$(date -u +%Y-%m-%dT%H:%M:%SZ) exit=${rc}" >> "${OUT}/browser-identity.txt"

started=$(sed -n 's/^started=//p' "${OUT}/browser-identity.txt")
cp "${WORK}/out/results.json" "${OUT}/results.json"
if [ -d "${WORK}/out/evidence" ]; then rm -rf "${OUT}/evidence"; cp -R "${WORK}/out/evidence" "${OUT}/evidence"; fi
cp "${PY36_R2_E6_LOG_ROOT:-/tmp/py36-r2-e6-20261010}/${RUNTIME}/fixture.txt" "${OUT}/fixture.txt" 2>/dev/null || true
mkdir -p "${OUT}/failure-screenshots"
find "${WORK}/out/test-results" -name 'test-failed-*.png' 2>/dev/null | while read -r png; do
    cp "${png}" "${OUT}/failure-screenshots/$(basename "$(dirname "${png}")").png"
done
{
    echo "# filtered from docker logs of py36-r2-e6-${RUNTIME}-{lms,cms,forum} since ${started}: lines matching Traceback|ERROR|Exception| 5xx status"
    for svc in lms cms forum; do
        docker container inspect "py36-r2-e6-${RUNTIME}-${svc}" >/dev/null 2>&1 || continue
        echo "== py36-r2-e6-${RUNTIME}-${svc}"
        docker logs --since "${started}" "py36-r2-e6-${RUNTIME}-${svc}" 2>&1 |
            grep -n -E 'Traceback|ERROR|Exception|" 5[0-9][0-9] ' || true
    done
} > "${OUT}/service-log-errors.txt"
rm -rf "${WORK}"
tail -n 5 "${OUT}/playwright.txt"
exit "${rc}"
