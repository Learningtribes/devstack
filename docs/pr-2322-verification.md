# PR #2322 Embargo Removal — Verification Results

> Date: 2026-07-21
> PR: #2322 embargo removal (M4.3 DCC)
> Branch: `embargo-removal` (worktree `platform-embargo-removal`)
> Runner: Playwright checklist-as-code (`browser-acceptance-harness`)
> Checklist: `checklists/pr-2322.yml` — 5 surfaces

---

## 1. PR Summary

61 files changed, 26 insertions, 3727 deletions.

| Layer | Change |
|-------|--------|
| Module | `openedx/core/djangoapps/embargo/` deleted (models, views, urls, middleware, admin) |
| Settings | `FEATURES['EMBARGO']`, `EMBARGO_SITE_REDIRECT_URL`, `EmbargoMiddleware`, `INSTALLED_APPS` removed from lms/cms common.py |
| URLs | `lms/urls.py`: `/embargo/` and `/api/embargo/` route blocks removed |
| API stub | `openedx/core/djangoapps/embargo/api.py` → `redirect_if_blocked()` always returns `None` (edx-enterprise compat) |
| Call-sites | `course_modes/views.py`, `student/views/management.py`, `verify_student/views.py`, `contentstore/tasks.py` stripped |
| Templates | `lms/templates/embargo/`, `static_templates/embargo.html` deleted |

---

## 2. Results

### embargo-removal branch — 5/5 passed (5.7s)

| # | Surface | Result |
|---|---------|:---:|
| 1 | admin RestrictedCourse → 404 | ✅ |
| 2 | admin IPFilter → 404 | ✅ |
| 3 | Studio /home/ 200 | ✅ |
| 4 | LMS / 200 | ✅ |
| 5 | choose course mode 200 | ✅ |

### Master baseline — 4 passed, 2 failed

| # | Surface | Master | embargo-rm | Role |
|---|---------|:---:|:---:|------|
| 1 | `/triboo-guanli/embargo/restrictedcourse/` | ❌ 200 | ✅ 404 | **discriminator** |
| 2 | `/triboo-guanli/embargo/ipfilter/` | ❌ 200 | ✅ 404 | **discriminator** |
| 3 | Studio `/home/` | ✅ 200 | ✅ 200 | gate |
| 4 | LMS `/` | ✅ 200 | ✅ 200 | gate |
| 5 | `/course_modes/choose/{course}/` | ✅ 200 | ✅ 200 | gate |

---

## 3. Discriminators

| # | Surface | Layer | Master | embargo-rm | Notes |
|---|---------|-------|:---:|:---:|-------|
| 1 | Admin RestrictedCourse | Admin routing | 200 | 404 | Model registered on master → admin page renders; deleted on embargo-rm → 404 |
| 2 | Admin IPFilter | Admin routing | 200 | 404 | Same pattern — ConfigurationModelAdmin, always registered |

Both are route-existence flips (non-404→404), requiring no fixture data. Admin gated on `DEBUG` (always true in devstack) — valid only where admin is enabled.

---

## 4. Vacuous Assertions (Removed)

**CountryAccessRule (`/triboo-guanli/embargo/countryaccessrule/`)**

Registered as `StackedInline` inside `RestrictedCourseAdmin`, never standalone via `admin.site.register()`. Returns 404 on BOTH branches → deleted from checklist after baseline proof.

**`/embargo/` and `/api/embargo/` routes**

Gated on `FEATURES['EMBARGO']` (default `False` on master) → not registered → 404 on both branches. Enabling the flag on master just to flip to non-404 is self-inflicted — use admin routing instead.

---

## 5. Gates (No Crash)

| Surface | Verifies |
|---------|----------|
| LMS `/` | No import error from embargo app removal |
| `/course_modes/choose/{course}/` | `embargo_api.redirect_if_blocked()` call-site stripped without crash |
| Studio `/home/` | CMS starts, no import error from `contentstore/tasks.py` embargo references |

---

## 6. Uncovered (Manual Only)

- `change_enrollment` POST — `embargo_api.redirect_if_blocked()` stripped in `student/views/management.py`
- `verify_student/views.py` — same call-site removal
- Course rerun in `contentstore/tasks.py` — `RestrictedCourse`/`CountryAccessRule` copy logic deleted
- `edx-enterprise` integration — consumes the API stub (`redirect_if_blocked` → `None`)

---

## 7. Run History

| Run | Branch | Result | Note |
|:---:|--------|:---:|------|
| 1 | embargo-rm | 6/6 | Initial (incl. vacuous CountryAccessRule) |
| 2 | master | 4/6 | Baseline — CountryAccessRule vacuous discovered |
| 3 | embargo-rm | 5/5 | CountryAccessRule deleted; verified stable |

---

## 8. Lessons

| # | Lesson |
|---|--------|
| 1 | **StackedInline ≠ standalone admin model.** CountryAccessRule was never registered with `admin.site.register()` → 404 on both branches. Always check `admin.py` registration before writing admin-route assertions. |
| 2 | **Route-gated URLs make poor discriminators.** `/embargo/` routes depend on `FEATURES['EMBARGO']` (default False). Turning the flag on just to discriminate is self-inflicted. Prefer always-active admin routes. |
| 3 | **API stub is not a deletion.** `embargo/api.py` was replaced with a stub, not removed. `text_absent` assertions on API-surface callers would be vacuous — the function still exists and is importable. |
| 4 | **Studio restart race.** After `enable_devstack.sh` restarts containers, Studio (:18010) takes ~20s longer than LMS (:18000) to become ready. Wait for `/signin` → 200/302 before running Studio surfaces. |

---

## 9. Cross-Reference

| Artifact | Location |
|----------|----------|
| Checklist YAML | `platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/pr-2322.yml` |
| PR worktree | `/Users/noahwang/workspace/hawthorn/platform-embargo-removal` |
| Runner | `platform-browser-acceptance-harness/.claude/skills/browser-acceptance/tests/checklist.spec.ts` |
| PR mount compose | `devstack/docker-compose-pr.yml` |
| PR #2323 results | `devstack/docs/pr-2323-verification.md` |
