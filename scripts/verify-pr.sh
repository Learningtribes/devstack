#!/bin/bash
# verify-pr.sh — Runtime verification pipeline for migration PRs
# Usage: ./verify-pr.sh <PR_NUMBER> <MODULE_PATH> [--smoke]
# Example: ./verify-pr.sh 2335 lms/djangoapps/grades
#          ./verify-pr.sh 2322 common/djangoapps/embargo --smoke

# NOTE: intentionally NOT using `set -e`. Test steps are expected to return
# non-zero on test failures, and we want to capture those exit codes and keep
# going rather than abort the whole pipeline mid-way.
set -uo pipefail

PR_NUM="${1:?Usage: $0 <PR_NUM> <MODULE_PATH> [--smoke]}"
MODULE="${2:?Usage: $0 <PR_NUM> <MODULE_PATH> [--smoke]}"
SMOKE=false
if [ "${3:-}" = "--smoke" ]; then
  SMOKE=true
fi

# Resolve the platform repo relative to this script (…/devstack/scripts → …/platform),
# with an env override. Avoids a hardcoded absolute path.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_DIR="${PLATFORM_DIR:-$(cd "${SCRIPT_DIR}/../../platform" 2>/dev/null && pwd || true)}"
if [ -z "${PLATFORM_DIR}" ] || [ ! -d "${PLATFORM_DIR}/.git" ]; then
  echo "Error: platform repo not found. Set PLATFORM_DIR=/path/to/platform." >&2
  exit 1
fi

# Determine PR type. Prefer an explicit override; otherwise infer from the
# actual diff against master (deleted files ⇒ DCC removal), falling back to the
# branch name. Branch-name grep alone misclassifies (e.g. a Py3 branch that
# merely touches entitlements).
BRANCH=$(cd "${PLATFORM_DIR}" && git rev-parse --abbrev-ref HEAD)
PR_TYPE="${PR_TYPE:-}"
if [ -z "${PR_TYPE}" ]; then
  DELETED_COUNT=$(cd "${PLATFORM_DIR}" && git diff master...HEAD --diff-filter=D --name-only 2>/dev/null | grep -c '\.py$' || true)
  if [ "${DELETED_COUNT:-0}" -gt 5 ]; then
    PR_TYPE="dcc"
  elif echo "$BRANCH" | grep -qE "removal|badges|embargo|support.*zendesk|entitlement|external_auth"; then
    PR_TYPE="dcc"
  else
    PR_TYPE="py3"
  fi
fi

echo "=== verify-pr.sh ==="
echo "PR:    #${PR_NUM}"
echo "Module: ${MODULE}"
echo "Type:   ${PR_TYPE}"
echo "Smoke:  ${SMOKE}"
echo ""

OUTDIR="/tmp/pr-${PR_NUM}"
mkdir -p "$OUTDIR"

# ── Step 1: Py2 Test (devstack LMS) ──
echo "── Step 1: Py2 test ──"
docker exec edx.devstack.lms bash -c "
  source /edx/app/edxapp/edxapp_env &&
  cd /edx/app/edxapp/edx-platform &&
  paver test_system -s lms -t ${MODULE} --fasttest --disable-migrations 2>&1
" > "${OUTDIR}/py2.out"
PY2_EXIT=$?
echo "Py2 exit: ${PY2_EXIT}"
grep -oE "[0-9]+ passed|[0-9]+ failed|ERROR|error" "${OUTDIR}/py2.out" | tail -3 || echo "(no summary)"
echo ""

# ── Step 2: Py3 Syntax Check ──
echo "── Step 2: Py3 syntax ──"
if docker ps --format '{{.Names}}' | grep -q py38-tool-container; then
  docker exec py38-tool-container bash -c "
    cd /work && source .venv/bin/activate 2>/dev/null || true &&
    python3 -m compileall -q ${MODULE}/ 2>&1
  " > "${OUTDIR}/py3_syntax.out" 2>&1
  SYNTAX_EXIT=$?
  if [ "${SYNTAX_EXIT}" -eq 0 ]; then
    echo "✓ Py3 syntax OK"
  else
    echo "✗ Py3 syntax errors:"
    grep "SyntaxError\|Error" "${OUTDIR}/py3_syntax.out" | head -5
  fi
else
  echo "⊗ py38-tool-container not running — skipping"
fi
echo ""

# ── Step 3: Py3 Test ──
# CAVEAT: full `test_system -s lms` under Py3.8 cannot boot until the celery 4.4 +
# driver Batch-1 bridge lands (see docs/py3-migration-environment.md §1). Until then
# this step is only meaningful for already-migrated pure-Python targets / test_lib;
# expect import/boot failures for un-migrated LMS modules (they are NOT a PR regression).
echo "── Step 3: Py3 test ──"
if docker ps --format '{{.Names}}' | grep -q py38-tool-container; then
  docker exec py38-tool-container bash -c "
    cd /work && source .venv/bin/activate 2>/dev/null || true &&
    SKIP_NPM_INSTALL=True paver test_system -s lms -t ${MODULE} \
      --fasttest --disable-migrations 2>&1
  " > "${OUTDIR}/py3.out"
  PY3_EXIT=$?
  echo "Py3 exit: ${PY3_EXIT}"
  grep -oE "[0-9]+ passed|[0-9]+ failed|ERROR|error" "${OUTDIR}/py3.out" | tail -3 || echo "(no summary)"
else
  echo "⊗ py38-tool-container not running — skipping"
fi
echo ""

# ── Step 4: Diff Summary ──
echo "── Step 4: Diff summary ──"
if [ -f "${OUTDIR}/py2.out" ] && [ -f "${OUTDIR}/py3.out" ]; then
  echo "Py2: $(grep -oE '[0-9]+ passed' "${OUTDIR}/py2.out" | head -1 || echo '?')"
  echo "Py3: $(grep -oE '[0-9]+ passed' "${OUTDIR}/py3.out" | head -1 || echo '?')"
  if grep -q "ERROR\|failed" "${OUTDIR}/py3.out"; then
    echo ""
    echo "⚠ Failures (Py3 only):"
    grep -oE "FAILED.*::test_\w+" "${OUTDIR}/py3.out" | head -10
  fi
fi
echo ""

# ── Step 5: Removal Residual Scan (DCC only) ──
if [ "${PR_TYPE}" = "dcc" ]; then
  echo "── Step 5: Removal residual scan ──"
  cd "${PLATFORM_DIR}"
  echo "Deleted files:"
  git diff master...HEAD --diff-filter=D --name-only 2>/dev/null | head -10 || echo "(no deletions)"
  echo "Installed apps changes:"
  git diff master...HEAD -- "*/envs/common.py" 2>/dev/null | grep "INSTALLED_APPS" | head -5 || echo "(none)"
  echo ""
fi

# ── Step 6: Browser acceptance (opt-in) ──
# Delegates to the platform `browser-acceptance` skill (Playwright Test/TS,
# checklist-as-code) — the single source of truth for UI assertions. This script
# only RUNS the per-PR checklist; the assertions live in the skill. Fixture prep
# (courses/content) is the separate concern in scripts/create_test_courses.py.
if [ "${SMOKE}" = true ]; then
  echo "── Step 6: Browser acceptance (skill checklist) ──"
  SKILL_DIR="${PLATFORM_DIR}/.claude/skills/browser-acceptance"
  CHECKLIST="${SKILL_DIR}/checklists/pr-${PR_NUM}.yml"
  BASE_URL="${BROWSER_ACCEPTANCE_BASE_URL:-http://localhost:18000}"
  if [ ! -d "${SKILL_DIR}" ]; then
    echo "⊗ browser-acceptance skill not found at ${SKILL_DIR} — skipping"
  elif [ ! -f "${CHECKLIST}" ]; then
    echo "⊗ no checklist pr-${PR_NUM}.yml — author one in ${SKILL_DIR}/checklists/ first (see its SKILL.md). Skipping."
  elif ! command -v npm >/dev/null 2>&1; then
    echo "⊗ npm not on PATH (need Node ≥18) — skipping"
  else
    echo "  (fixtures required: run the skill's enable_devstack.sh + provision-fixtures.sh once)"
    (
      cd "${SKILL_DIR}" &&
      { [ -d node_modules ] || npm install >/dev/null 2>&1; } &&
      BROWSER_ACCEPTANCE_BASE_URL="${BASE_URL}" CHECKLIST_PR="pr-${PR_NUM}" \
        npm run --silent checklist
    ) > "${OUTDIR}/browser.out" 2>&1
    BROWSER_EXIT=$?
    echo "Browser exit: ${BROWSER_EXIT}"
    grep -E "[0-9]+ passed|[0-9]+ failed|✓|✘|✗" "${OUTDIR}/browser.out" | tail -6 || echo "(no summary — see ${OUTDIR}/browser.out)"
  fi
fi

echo "Done. Output: ${OUTDIR}/"
ls -la "${OUTDIR}/"
