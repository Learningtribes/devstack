# PR Verification — Execution Results

> Date: 2026-07-20  
> PR: #2323 badges removal  
> Branch: `browser-acceptance-harness` (checklist runner) + `badges-removal` (PR worktree)  
> Tool: Playwright Test/TS + checklist-as-code runner
>
> **Run 1:** 4/9. **Run 2:** 5/8. **Run 3:** master baseline, surface 1 discriminator.  
> **Run 4:** 6/8 (surface 3 retarget + admin 404 — but admin false positive, §6.8).  
> **Run 5:** Master baseline with corrected `/triboo-guanli/` URL — **2 discriminators proven (surfaces 1 + 9).**  
> **Run 6:** badges-rm final — surface 2 deleted, 5/7 passed.  
> **Run 7:** studioAuth form-login attempt — WRONG root cause, reverted (§6.13).  
> **Run 8:** Studio auth fixed at root — 7/7 green incl. both Studio surfaces.  
> **Run 9:** Master baseline — surface 6 confirmed as gate (passes on master too).  
> Checklist: 7 surfaces. **2 discriminators proven (1 + 9).** Surface 6 = gate, not discriminator.  
> **Canonical final state + reusable lessons: see §7 and the skill's `SKILL.md` ("Hard-won rules").**
> Historical run tables below use the original 9-surface numbering; §7 maps it to the committed 7-surface checklist.

---

## 1. Setup

```bash
export PLATFORM_MOUNT=/Users/noahwang/workspace/hawthorn/platform-badges-removal
docker compose -f docker-compose.yml -f docker-compose-pr.yml up -d lms studio
git checkout -- lms/envs/devstack_docker.py cms/envs/devstack_docker.py
bash scripts/enable_devstack.sh
bash scripts/provision-fixtures.sh
# Registration + superuser for edx
# Note: docker-compose-pr.yml mounts ${DEVSTACK_WORKSPACE}/src:/edx/src (themes ship under it
#       at /edx/src/themes — no separate themes mount needed; see §6.12)
BROWSER_ACCEPTANCE_BASE_URL=http://localhost:18000 CHECKLIST_PR=pr-2323 npm run checklist
```

---

## 2. Results

### Run 6 — badges-removal final, surface 2 deleted (13.6s)

| # | Surface | Result |
|---|---------|:---:|
| 1 | Badges API 404 | ✅ |
| 3 | User API — accomplishments_shared | ✅ |
| 4 | LMS homepage 200 | ✅ |
| 5 | Cert share buttons | ✅ |
| 9 | Admin badges 404 | ✅ |
| 7 | Studio home | ❌ (302) |
| 8 | Studio advanced settings | ❌ (302) |

**5/7 passed on badges-removal. 2 Studio blocked by CMS auth.**

### Run 5 — Master baseline (45.8s)

| # | Surface | Master | badges-rm | Discriminates? |
|---|---------|:---:|:---:|:---:|
| 1 | Badges API | 🔴 200 | ✅ 404 | ✅ **proven** |
| 9 | Admin `/triboo-guanli/badges/badgeclass/` | 🔴 302 | ✅ 404 | ✅ **proven** |
| 2 | Profile badge container | ✅ absent | ✅ absent | ❌ vacuous → deleted Run 6 |
| 3 | User API — accomplishments_shared | ✅ present | ✅ present | ⚠️ gate |
| 7/8 | Studio | ❌ 302/403 | ❌ 302/403 | auth block |

### Run progression

| Run | Branch | Change | Result |
|:---:|--------|--------|:---:|
| 1 | badges-rm | Initial | 4/9 |
| 2 | badges-rm | env corrections | 5/8 |
| 3 | master | Baseline (old surface 3/9) | 1 discriminator |
| 4 | badges-rm | Surface 3 retarget + admin URL | 6/8 |
| 5 | master | Corrected `/triboo-guanli/` URL | 2 discriminators |
| 6 | badges-rm | Surface 2 deleted + `/edx/src` mount fix | 5/7 (stable) |
| 7 | badges-rm | studioAuth form-login attempt (wrong root cause) | reverted |
| 8 | badges-rm | autoAuth staff/superuser + shared session | **7/7 (Studio green)** |
| 9 | master | Baseline — surface 6 confirmation | 5/7 pass, surface 6 = gate |

---

## 3. Discriminators

### Proven (measured on both branches)

| # | Surface | Layer | Master | badges-rm | Status |
|---|---------|-------|:---:|:---:|--------|
| 1 | `/api/badges/v1/assertions/user/{user}/` | URL routing | 200 | 404 | ✅ **proven** |
| 9 | `/triboo-guanli/badges/badgeclass/` | Admin routing | 302 | 404 | ✅ **proven** — env-dependent (§6.10) |

### Candidate / Pending (NOT yet proven)

| # | Surface | Layer | Master | badges-rm | Blocker |
|---|---------|-------|:---:|:---:|--------|
| 3 | `accomplishments_shared` value | serializer | `true` | `false` | current assertion is gate only. Upgrade to value + re-baseline (§6.5) |
| 8 | Studio `issue_badges` toggle | CMS settings | present | absent | **now EXECUTES & passes on badges-rm (Run 8)** — master baseline pending to confirm it discriminates (double-run rule) |

**Proven count: 2 (surfaces 1 + 9).**

---

## 4. Issues Encountered

| # | Issue | Resolution |
|---|-------|-----------|
| 1 | `edx` auto_auth 500 — no Registration | `Registration.objects.get_or_create(user=edx)` |
| 2 | `SOCIAL_SHARING_SETTINGS` misdiagnosis | Var IS defined; polluted `devstack_docker.py`. Clean + re-enable. |
| 3 | Worktree flags | `enable_devstack.sh` after each switch |
| 7 | `devstack_docker.py` polluted | `git checkout --` then `enable_devstack.sh` once |
| 8 | Studio 302 | **Root cause (verified): NOT a cookie problem.** LMS & CMS both use `SESSION_COOKIE_NAME='sessionid'` + shared session store (proven: LMS `/auto_auth` cookie jar → `:18010/home/` = 200). The runner's `autoAuth` never passed `staff`/`superuser`, so each edx login demoted the user → Studio 302. **Fixed:** `autoAuth` forwards staff/superuser; no CMS login needed. |
| 9 | Admin at wrong URL | **FIXED:** `/triboo-guanli/badges/badgeclass/` ✅ |
| 10 | Surface 3 gate, not discriminator | Upgrade to value assertion (§6.5) |
| 11 | `docker-compose-pr.yml` OSError on theme dir after worktree switch | **Real fix = the `${DEVSTACK_WORKSPACE}/src:/edx/src` mount** (themes live under it at `/edx/src/themes`; canonical `docker-compose-host.yml` mounts only `/edx/src`, no separate themes line). The `src/themes:/edx/src/themes` line briefly added in Run 6 was a **redundant no-op** (same host subpath, target nested inside `/edx/src`). ✅ **Resolved:** redundant line removed; only `/edx/src` remains (§6.12). |
| 12 | Surface 2 flaky + vacuous | **DELETED.** No BadgeAssertion fixture + page timeout on master. (Note: the Run-6 delete commit only removed a comment; the `/u/{username}` surface was actually removed from `checklists/pr-2323.yml` in the skill afterwards → checklist now truly 7 surfaces, matching this log.) |
| 13 | ~~Studio auth — form-login `waitForNavigation` timeout~~ | **Obsolete — studioAuth REVERTED (§6.13).** It chased a non-existent problem (form login on an unverified cookie theory). Real fix was one line in `autoAuth` (pass staff/superuser). Shared LMS↔CMS session then authenticates Studio directly. |

---

## 5. Next Steps (handoff — actionable)

1. ✅ All env corrections — surfaces 1, 4, 5 green on badges-rm.
2. ✅ Master baseline — surfaces 1 + 9 double-proven.
3. ✅ Surface 2 deleted (flaky+vacuous).
4. ✅ `docker-compose-pr.yml` mount fix — added `/edx/src`, removed the redundant `src/themes` overlay (§6.12).
5. ⚠️ Surface 3: upgrade gate to value assertion + re-baseline both branches.
6. ✅ Studio auth fixed at root (§6.1/§6.13) — `autoAuth` staff/superuser + shared session → both Studio surfaces green (Run 8). Remaining: run the **master baseline** to confirm surface 6 (`issue_badges`) discriminates (per the double-run rule).
7. §6.10 — gate surface 9 on `ENABLE_DJANGO_ADMIN_SITE`.
8. §6.6 — split surface 5 OpenBadges half.
9. Apply to PRs #2322/#2324/#2348.

---

## 6. Review corrections

### 6.1 Studio 302 — root cause (verified on live devstack)
**Not a cookie problem, and NOT "distinct CMS cookie" (that earlier claim was wrong).**
Verified: LMS and CMS both use `SESSION_COOKIE_NAME='sessionid'` and the same session
store; reusing an LMS `/auto_auth` cookie jar on `http://localhost:18010/home/` returns
**200**. CMS has no `/auto_auth` route (and `AUTOMATIC_AUTH_FOR_TESTING` is False there),
so a CMS auto_auth was never the answer either. The real bug: the runner's `autoAuth`
omitted `staff`/`superuser`, so every edx login demoted the user → Studio 302. **Fix:**
`USERS.edx` carries `staff`/`superuser` and `autoAuth` forwards them; the shared session
then authenticates Studio with no extra login. (Run 8: 7/7 green.)

### 6.5 Surface 3 — upgrade to value assertion
Diff: `accomplishments_shared = badges_enabled()` → `= False`. Current assertion `text_present: accomplishments_shared` is gate (passes both). Assert VALUE: `"accomplishments_shared": false` vs `true`.

### 6.6 Surface 5 vacuous half
Cert bundles share buttons (live gate) + OpenBadges absent (vacuous under `issue_badges=False`).

### 6.8 Admin URL — FIXED in Run 5
Triboo fork admin at `/triboo-guanli/`. Corrected to `/triboo-guanli/badges/badgeclass/`. ✅

### 6.9 Process rule
Every retarget must be re-run on BOTH master and badges-rm.

### 6.10 Surface 9 env-dependent
Admin routed only when `settings.DEBUG or FEATURES['ENABLE_DJANGO_ADMIN_SITE']`. Gate surface 9 on this flag.

### 6.11 Run 5 verdict — accepted
Surface 9's 302→404 is auth-independent route-existence flip. **2 discriminators proven.**

### 6.12 `docker-compose-pr.yml` themes mount was redundant — RESOLVED
Canonical `docker-compose-host.yml` mounts only `${DEVSTACK_WORKSPACE}/src:/edx/src:cached`;
themes are served under it at `/edx/src/themes`. The Run-6 line
`${DEVSTACK_WORKSPACE}/src/themes:/edx/src/themes:cached` targeted a path **nested inside**
`/edx/src` pointing to the **same host subpath** → a no-op overlay. The OSError was actually
caused by a missing `/edx/src` mount, not a missing themes mount. ✅ **Resolved:** the
`src/themes` line was removed from both `lms` and `studio`; only `/edx/src` remains (matches
host.yml).

### 6.13 studioAuth — REVERTED (Run 8); Studio auth fixed at the root

Run 7's `studioAuth` (CMS `/signin` form login) was built on the disproven §6.1 cookie
theory and is **removed** (`lib/auth.ts` back to a single `autoAuth`). It was also fragile
on its own terms: hardcoded password, deprecated `waitForNavigation`, and logistration
(React/Backbone) selectors that a classic `input[name=...]`/`button[type=submit]` form fill
does not reliably match.

Root fix instead (Run 8): `autoAuth` now forwards `staff`/`superuser` for `edx`, and the
shared LMS↔CMS `sessionid` session covers Studio — **7/7 green, both Studio surfaces
included**. Lesson (now in `SKILL.md`): verify the root cause with a 2-minute cookie-jar
probe before building a login subsystem.

### 6.7 Priority order
1. ✅ Surface 1 + 9 double-proven.
2. ⚠️ Surface 3 value assertion upgrade.
3. 🔒 CMS auto_auth → surface 8.
4. Split surface 5.
5. Apply to #2322/#2324/#2348.

---

## 7. Canonical final state (committed checklist)

The committed `checklists/pr-2323.yml` now has **7 surfaces, renumbered 1–7** (the
old 8/9 numbering used in the run tables above is historical). The vacuous
`/u/{username}` profile surface was **actually removed** in the skill (commit
`0fb459e91c8`; the earlier Run-6 "delete" only stripped a comment). Checklist
annotations are now **self-contained** — they no longer cross-reference this log's
`§` numbers.

| New # | id (checklist order) | Role | Notes |
|:---:|------|------|-------|
| 1 | badges API returns 404 | ✅ **discriminator** | URL routing, 200→404 |
| 2 | user API `accomplishments_shared` | ⚠️ gate | field retained; value flip is the real discriminator (§6.5) |
| 3 | LMS homepage 200 | gate | no import error |
| 4 | cert page + share controls | gate | share buttons live; badge markers dropped (were vacuous) |
| 5 | Studio home | gate | ✅ executes (Run 8, shared session) |
| 6 | Studio advanced settings | ⚠️ candidate | ✅ executes & passes on badges-rm (Run 8); master baseline pending to confirm `issue_badges` discriminates |
| 7 | admin `/triboo-guanli/badges/badgeclass/` | ✅ **discriminator** | env-gated on `ENABLE_DJANGO_ADMIN_SITE` (§6.10); non-404→404 |

**Reusable lessons** (discriminator-vs-gate, double-run every retarget, fork-relocated
/ env-gated URLs, per-origin Studio auth, reset polluted `devstack_docker.py`) now live
in the skill's `SKILL.md` → *Hard-won rules*, so they travel with the skill to other
removal PRs. This log stays as the #2323-specific run evidence.

### Cross-artifact correspondence (verify before merging either side)

| Artifact | Repo / branch | Carries |
|----------|---------------|---------|
| `SKILL.md`, `checklists/pr-2323.yml`, `lib/auth.ts` | platform / `browser-acceptance-harness` (HEAD `540e34505cd`, not pushed) | assertions + auth + reusable rules |
| `docker-compose-pr.yml`, `verify-pr.sh`, this log | devstack / `noah-py2-m-chip-master` (commit `c44320c`, not pushed) | infra + run evidence |
| PR under test | platform / `badges-removal` | #2323 |
