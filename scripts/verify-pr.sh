#!/bin/bash
# verify-pr.sh — Runtime verification pipeline for migration PRs
# Usage: ./verify-pr.sh <PR_NUMBER> <MODULE_PATH> [--smoke]
# Example: ./verify-pr.sh 2335 lms/djangoapps/grades
#          ./verify-pr.sh 2322 common/djangoapps/embargo --smoke

set -euo pipefail

PR_NUM="${1:?Usage: $0 <PR_NUM> <MODULE_PATH> [--smoke]}"
MODULE="${2:?Usage: $0 <PR_NUM> <MODULE_PATH> [--smoke]}"
SMOKE=false
if [ "${3:-}" = "--smoke" ]; then
  SMOKE=true
fi

# Determine PR type from branch name
BRANCH=$(cd /Users/noahwang/workspace/hawthorn/platform && git rev-parse --abbrev-ref HEAD)
PR_TYPE="py3"
if echo "$BRANCH" | grep -q "removal\|badges\|embargo\|support.*zendesk\|entitlement\|external_auth"; then
  PR_TYPE="dcc"
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
  cd /Users/noahwang/workspace/hawthorn/platform
  echo "Deleted files:"
  git diff master...HEAD --diff-filter=D --name-only 2>/dev/null | head -10 || echo "(no deletions)"
  echo "Installed apps changes:"
  git diff master...HEAD -- "*/envs/common.py" 2>/dev/null | grep "INSTALLED_APPS" | head -5 || echo "(none)"
  echo ""
fi

# ── Step 6: Browser Smoke ──
if [ "${SMOKE}" = true ]; then
  echo "── Step 6: Browser smoke ──"
  cd /Users/noahwang/workspace/hawthorn/devstack
  python3 scripts/create_test_courses.py --dry-run 2>&1 | tail -3 || echo "(Playwright unavailable)"
fi

echo "Done. Output: ${OUTDIR}/"
ls -la "${OUTDIR}/"
