# PR Runtime Verification Pipeline

> Date: 2026-07-19  
> Prerequisites: local devstack running + Py38 test container available

---

## 1. Problem

Open migration PRs pass CI syntax checks but have zero runtime verification. The unit tests and full regression are manual `workflow_dispatch` — effectively never run. This pipeline fills the gap.

---

## 2. Pipeline Steps

```
Checkout PR branch
  │
  ├─ Step 1: Py2 targeted test       devstack (lms container)
  ├─ Step 2: Py3 syntax + test       py38-tool-container
  ├─ Step 3: Diff comparison         host (compare outputs)
  ├─ Step 4: Removal residual scan   host (for DCC PRs only)
  └─ Step 5: Browser smoke           host → devstack (Playwright)
```

---

## 3. Per-PR Quick Start

### 3.1 Setup

```bash
cd /Users/noahwang/workspace/hawthorn/platform
git fetch origin
PR_NUM=XXXX  # set PR number
git checkout -b verify-pr-${PR_NUM} origin/master  # cut from master
# Option A: merge the PR branch into master-equivalent
git merge --no-edit origin/<pr-branch-name>
# Option B: checkout the PR branch directly
git checkout origin/<pr-branch-name>
```

### 3.2 Run Pipeline

```bash
MODULE=<module-under-test>  # e.g. lms/djangoapps/grades
./devstack/scripts/verify-pr.sh ${PR_NUM} ${MODULE}
```

---

## 4. Step Details

### Step 1 — Py2 Test (devstack LMS)

```bash
docker exec edx.devstack.lms bash -c "
  source /edx/app/edxapp/edxapp_env &&
  cd /edx/app/edxapp/edx-platform &&
  paver test_system -s lms -t ${MODULE} --fasttest --disable-migrations 2>&1
" > /tmp/py2-${PR_NUM}.out
echo "Py2 exit: $?"
```

### Step 2 — Py3 Syntax + Test (test container)

```bash
# 2a: Syntax check
docker exec py38-tool-container bash -c "
  cd /work && source .venv/bin/activate &&
  python3 -m compileall -q ${MODULE}/ 2>&1
" | grep -v "^Listing"  # suppress listing noise

# 2b: Unit test
docker exec py38-tool-container bash -c "
  cd /work && source .venv/bin/activate &&
  SKIP_NPM_INSTALL=True paver test_system -s lms -t ${MODULE} \
    --fasttest --disable-migrations 2>&1
" > /tmp/py3-${PR_NUM}.out
echo "Py3 exit: $?"
```

### Step 3 — Diff Comparison

```bash
echo "=== Pass/Fail summary ==="
grep -oE "[0-9]+ passed|[0-9]+ failed|error" /tmp/py2-${PR_NUM}.out | tail -1
grep -oE "[0-9]+ passed|[0-9]+ failed|error" /tmp/py3-${PR_NUM}.out | tail -1

echo "=== Diffs (test names only) ==="
diff <(grep -oE "::test_\w+" /tmp/py2-${PR_NUM}.out | sort) \
     <(grep -oE "::test_\w+" /tmp/py3-${PR_NUM}.out | sort)
```

### Step 4 — Removal Residual Scan (DCC PRs only)

Per CLAUDE.md module removal patterns (§12):

```bash
# 4a: Check for import residuals
git diff master...HEAD --name-only | grep "\.py$" | xargs grep -l "import.*from.*removed_module" || echo "No residual imports"

# 4b: Check settings references
git diff master...HEAD | grep -E "^\+\s*(INSTALLED_APPS|FEATURES|MIDDLEWARE)" || echo "No settings changes"

# 4c: Check URL patterns
git diff master...HEAD --name-only | grep "url" | xargs grep -l "removed_app" || echo "No URL residuals"

# 4d: Check template references
git diff master...HEAD --name-only | grep "html\|mako\|underscore" | xargs grep -l "removed_feature" || echo "No template residuals"
```

### Step 5 — Browser Smoke

```bash
python3 devstack/scripts/create_test_courses.py --dry-run 2>&1
# For removal PRs affecting specific pages:
# python3 -c "from playwright.sync_api import sync_playwright; ..."  # targeted check
```

---

## 5. CI Integration (Future)

When the Py38 test container is stable, this pipeline can run as a GitHub Actions workflow:

```yaml
# .github/workflows/pr-runtime-verification.yml
name: PR Runtime Verification
on:
  pull_request:
    paths:
      - 'lms/**'
      - 'cms/**'
      - 'common/**'
jobs:
  py2-tests:
    runs-on: ubuntu-latest
    services:
      mysql: ...
      mongo: ...
    steps:
      - uses: actions/checkout@v4
      - run: paver test_system -s lms --fasttest
  py3-tests:
    runs-on: ubuntu-latest
    container: python:3.8-bullseye
    steps:
      - uses: actions/checkout@v4
      - run: ./setup-py38-container.sh && paver test_system -s lms --fasttest
```

---

## 6. Per-PR Verification Matrix

| PR | Type | Modules to Test | Removal Scan | Browser Smoke |
|----|------|-----------------|:-----------:|:------------:|
| #2322 embargo | DCC | `common/djangoapps/embargo` | ✅ | Studio → Advanced Settings |
| #2323 badges | DCC | `lms/djangoapps/badges`, `openedx/features/badging` | ✅ | LMS → Profile |
| #2324 support+zendesk | DCC | tests only (no production code) | ✅ | — |
| #2334 triboo_analytics | Py3 | `openedx/features/triboo_analytics` | ❌ | LMS Dashboard |
| #2335 grades | Py3 | `lms/djangoapps/grades` | ❌ | LMS Grades page |
| #2347 ur-regex | Py3 | `importlib` import chain (5 files) | ❌ | LMS login |
| #2348 M4.4-A | DCC | `common/djangoapps/entitlements`, `openedx/core/djangoapps/external_auth` | ✅ | Studio → Certificates |

---

## 7. AI-Assisted Automation

With Hermes Agent, the pipeline becomes:

```
User: "verify PR #2335"  →  Agent:
  1. git checkout pr branch
  2. Run verify-pr.sh 2335 lms/djangoapps/grades
  3. Report: "Py2: 47 passed. Py3: 44 passed, 3 failed (encoding issues in test_fixtures.py)"
  4. Optionally auto-fix the 3 failures if pattern is known
```

The verify-pr.sh script is the key enabler — it wraps all 4 steps into a single command that an AI agent can invoke.
