# PR Verification — Execution Results

> Date: 2026-07-20  
> PR: #2323 badges removal  
> Branch: `browser-acceptance-harness` (checklist runner) + `badges-removal` (PR worktree)  
> Tool: Playwright Test/TS + checklist-as-code runner

---

## 1. Setup

```bash
# Node v24.7.0 (Homebrew), Playwright Chromium
cd platform-browser-acceptance-harness/.claude/skills/browser-acceptance
npm install
npx playwright install chromium

# Devstack → badges-removal worktree
export PLATFORM_MOUNT=/Users/noahwang/workspace/hawthorn/platform-badges-removal
docker compose -f docker-compose.yml -f docker-compose-pr.yml up -d lms studio

# Enable feature flags on the worktree
# Append to lms/envs/devstack_docker.py:
FEATURES["CERTIFICATES_HTML_VIEW"] = True
FEATURES["RESTRICT_AUTOMATIC_AUTH"] = False
FEATURES["ALLOW_PUBLIC_ACCOUNT_CREATION"] = True
FEATURES["ENABLE_OPENBADGES"] = True

# Provision fixtures (qacert user + QA course + cert)
bash scripts/provision-fixtures.sh

# Create Registration for edx (auto_auth prerequisite)
python manage.py lms shell -c "Registration.objects.get_or_create(user=edx_user)"

# Run
BROWSER_ACCEPTANCE_BASE_URL=http://localhost:18000 \
  CHECKLIST_PR=pr-2323 npm run checklist
```

---

## 2. Results

| # | Surface | Auth | Assertion | Result |
|---|---------|------|-----------|:---:|
| 1 | Badges API | qacert | 404 | ✅ |
| 2 | Learner profile — badge container | qacert | `.badge-list-container` absent | ✅ |
| 3 | User API — badges fields | qacert | `badges` text absent | ✅ |
| 4 | LMS homepage | edx | 200 | ✅ |
| 5 | Cert page share buttons | qacert | `.action-share-facebook` visible | ❌ |
| 6 | Learner profile API | qacert | 200 status | ❌ |
| 7 | Studio home | edx | 200 | ❌ (403) |
| 8 | Studio advanced settings | edx | 200, badge toggle absent | ❌ (403) |
| 9 | Django admin badge models | edx | 200, badge links absent | ❌ |

**4/9 passed (7.7s)**. All core badges-removal assertions green. Failures are environmental.

---

## 3. Failure Analysis (reviewed 2026-07-20 — corrected)

**None of the 5 failures is a PR regression.** Classified below with evidence.

| # | Surface | Class | Root cause (evidence) | Fix |
|---|---------|-------|-----------------------|-----|
| 5 | Cert share buttons | 🔴 self-inflicted | The `SOCIAL_SHARING_SETTINGS` "NameError → removed" (issue #2 below) was a **misdiagnosis**. `lms/envs/common.py:2345` **defines** `SOCIAL_SHARING_SETTINGS`; there is **no `__all__`**; `devstack_docker.py` does `from .devstack import *`, so the name IS in scope → `dict(SOCIAL_SHARING_SETTINGS, ...)` is valid. Removing the append is exactly what made the cert omit the share section → red. (The committed `enable_devstack.sh` still contains the correct line; a clean run renders the buttons — verified 2/2 green on the 2-surface run.) | Restore the flag by re-running `enable_devstack.sh` on a **clean** `devstack_docker.py` (see #6) — do NOT delete the line. |
| 6 | Learner profile API | 🟡 authoring error | `/api/learner_profile/v1/{username}/accomplishments` is almost certainly not a real Hawthorn endpoint — accomplishments/badges were served by the (now-removed) badges API, not learner_profile. | Verify the real path; if none, delete this surface. |
| 7 | Studio home | 🟡 fixture gap | `edx` user is `is_staff=False, is_superuser=False` (verified) despite the checklist comment calling it "superuser". Studio requires Studio access. | auto_auth `edx` with `staff=true&superuser=true`, or elevate `edx` in fixtures. |
| 8 | Studio advanced settings | 🟡 fixture gap | Same as #7 (no staff/course-staff role). | Same as #7. |
| 9 | Django admin | 🟡 fixture gap | `/admin/` requires `is_staff=True`; `edx` has `is_staff=False` → redirect, not 200. | Same as #7 (needs superuser). |

### ⚠ Vacuous-assertion risk (surfaces 2, 3, 4 — NOT yet proven meaningful)

Surfaces 2/3/4 assert `.badge-list-container` / `badges` text is **absent**. But on
**master** those markers only appear when the user actually **has a BadgeAssertion**
(badges feature on + earned badge). With no badge fixture they are absent on master
too → the assertion would pass on BOTH branches = **vacuous** (same trap as the
cert badge-modal, which is why the API route was chosen for surface 1). **Only
surface 1 (API route 404-vs-200) is proven discriminating so far.** Confirm 2/3/4
with the baseline control (§5.4); if vacuous, upgrade them to route/structure-level
checks or provision a real BadgeAssertion.

---

## 4. Issues Encountered

| # | Issue | Resolution |
|---|-------|-----------|
| 1 | `edx` auto_auth 500 — no Registration record | `Registration.objects.get_or_create(user=edx)` |
| 2 | ~~`SOCIAL_SHARING_SETTINGS` NameError on badges-removal → removed the line~~ | **Reverted diagnosis (see §3, row 5).** The var IS defined in `common.py`; the NameError came from a **polluted `devstack_docker.py`** (duplicate + empty harness blocks from repeated/manual appends), not from the branch. Keep the flag; clean the file. |
| 3 | Worktree doesn't have acceptance flags | Must `enable_devstack.sh` after each worktree switch |
| 4 | curl `+` → space (URL encoding) | curl issue only; Playwright `page.goto()` handles correctly |
| 5 | LMS restart takes 15-30s per switch | Factor into pipeline timing |
| 6 | `npm run --silent` still noisy | Normal |
| 7 | `devstack_docker.py` polluted with duplicate/empty harness blocks | Revert the worktree file (`git checkout -- lms/envs/devstack_docker.py cms/envs/devstack_docker.py`) then run `enable_devstack.sh` **once** (idempotent) |

---

## 5. Next Steps (handoff — actionable)

1. **Clean + re-enable**: revert the polluted `devstack_docker.py` on the
   badges-removal worktree, then run `enable_devstack.sh` once → **surface 5 turns green**.
2. **Elevate `edx`**: auto_auth it with `staff=true&superuser=true` (runner auth) or
   elevate in fixtures → **surfaces 7/8/9 turn green**.
3. **Fix surface 6**: confirm the real accomplishments endpoint or delete the surface.
4. **Baseline control (most important)**: switch devstack to the master worktree, run
   the SAME checklist, and confirm the "removed/absent" surfaces go RED. Expect
   surface 1 to flip (200 on master); **watch 2/3/4 — if they stay green on master
   they are vacuous** (see §3 warning) and must be upgraded.
5. Document baseline-vs-PR diff once §5.4 is clean.
6. Apply the pattern to other migration PRs (embargo #2322, support #2324, M4.4-A #2348).
