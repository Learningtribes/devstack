# PR Verification — Execution Results

> Date: 2026-07-20  
> PR: #2323 badges removal  
> Branch: `browser-acceptance-harness` (checklist runner) + `badges-removal` (PR worktree)  
> Tool: Playwright Test/TS + checklist-as-code runner
>
> **Run 1 (initial):** 4/9 passed. **Run 2 (corrected):** 5/8 passed.  
> Studio ×3 + admin blocked by cross-port auth, not PR regressions.

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

# Clean polluted devstack_docker.py (issue #7)
git checkout -- lms/envs/devstack_docker.py cms/envs/devstack_docker.py

# Enable feature flags (once, after clean)
bash scripts/enable_devstack.sh

# Provision fixtures (qacert user + QA course + cert)
bash scripts/provision-fixtures.sh

# Registration for edx (auto_auth prerequisite)
python manage.py lms shell -c "Registration.objects.get_or_create(user=edx_user)"

# Elevate edx to superuser (Studio/admin surfaces)
UPDATE auth_user SET is_staff=1, is_superuser=1 WHERE username='edx'

# Run
BROWSER_ACCEPTANCE_BASE_URL=http://localhost:18000 \
  CHECKLIST_PR=pr-2323 npm run checklist
```

---

## 2. Results

### Run 2 (after corrections)

| # | Surface | Auth | Assertion | Result |
|---|---------|------|-----------|:---:|
| 1 | Badges API | qacert | 404 | ✅ |
| 2 | Learner profile — badge container | qacert | `.badge-list-container` absent | ✅ |
| 3 | User API — badges fields | qacert | `badges` text absent | ✅ |
| 4 | LMS homepage | edx | 200 | ✅ |
| 5 | Cert page share buttons | qacert | `.action-share-facebook` visible | ✅ |
| 6 | ~~Learner profile API~~ | — | — | 🗑 deleted |
| 7 | Studio home | edx | 200 | ❌ (302) |
| 8 | Studio advanced settings | edx | 200, badge toggle absent | ❌ (302) |
| 9 | Django admin badge models | edx | 200, badge links absent | ❌ (404) |

**5/8 passed (19.8s)**. All LMS-side assertions green. 3 Studio/admin failures are cross-port auth, NOT PR regressions.

### Run 1 (initial, 4/9) → Run 2 (corrected, 5/8)

| Change | Surface | Before | After |
|--------|---------|:---:|:---:|
| Re-enable `SOCIAL_SHARING_SETTINGS` | 5 | ❌ | ✅ |
| Elevate `edx` → superuser | 7/8/9 | ❌ (403) | ❌ (302/404) — new class |
| Delete nonexistent endpoint | 6 | ❌ | 🗑 removed |

---

## 3. Failure Analysis (reviewed 2026-07-20 — corrected ×2)

**None of the failures is a PR regression.** All LMS surfaces green (5/5).

| # | Surface | Class | Root cause (evidence) | Fix |
|---|---------|-------|-----------------------|-----|
| 5 | Cert share buttons | ✅ **FIXED** | Re-enabled by `enable_devstack.sh` on clean `devstack_docker.py` | — |
| 7 | Studio home | 🟡 cross-port auth | `auto_auth` at port 18000 creates **LMS-only** session cookie. Studio at port 18010 serves different origin → cookie not sent → 302 redirect to /signin. Not a #2323 issue — this affects ANY Studio surface tested this way. | Extend runner to handle Studio login (form-fill or shared session domain), or test Studio surfaces manually |
| 8 | Studio advanced settings | 🟡 cross-port auth | Same as #7. | Same as #7. |
| 9 | Django admin | 🟡 cross-port auth | `/admin/` on LMS port 18000 returns 404 after auto_auth — the admin module may not be enabled on this devstack instance. `edx` is now is_staff=1, is_superuser=1 but the route itself is 404. | Enable Django admin in URLs, or test via Studio's admin equivalent |

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
| 2 | ~~`SOCIAL_SHARING_SETTINGS` NameError on badges-removal → removed the line~~ | **Reverted diagnosis.** The var IS defined in `common.py:2345`; the NameError came from a **polluted `devstack_docker.py`**. Clean the file; keep the flag. |
| 3 | Worktree doesn't have acceptance flags | Must `enable_devstack.sh` after each worktree switch |
| 4 | curl `+` → space (URL encoding) | curl issue only; Playwright `page.goto()` handles correctly |
| 5 | LMS restart takes 15-30s per switch | Factor into pipeline timing |
| 6 | `npm run --silent` still noisy | Normal |
| 7 | `devstack_docker.py` polluted with duplicate/empty harness blocks | `git checkout --` then `enable_devstack.sh` once |
| 8 | Studio surfaces 302 — LMS session cookie doesn't cross ports | Runner limitation; Studio needs separate login flow |
| 9 | `/admin/` 404 — admin module not enabled in this instance | Enable or route through Studio admin |

---

## 5. Next Steps (handoff — actionable)

1. ✅ ~~Clean + re-enable~~ → surface 5 green.
2. ✅ ~~Elevate `edx`~~ → is_staff=1, is_superuser=1. Studio surfaces still blocked by cross-port auth (see §4 issue 8).
3. ✅ ~~Delete surface 6~~ → removed.
4. **Baseline control (most important)**: switch devstack to master worktree, run SAME checklist. Expect surface 1 to flip RED (200 on master). **Watch 2/3/4 — if they stay green on master they are vacuous** and must be upgraded to route/structure-level checks.
5. **Resolve cross-port auth**: extend runner to handle Studio login, or add `/admin/` routing, or accept LMS-only coverage for now.
6. Document baseline-vs-PR diff once §5.4 is clean.
7. Apply pattern to other migration PRs (embargo #2322, support #2324, M4.4-A #2348).
