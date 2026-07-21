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
> **Run 9:** Master baseline (old HTML assertion) — surface 6 false gate, CodeMirror artifact (§6.14).  
> **Run 10/11:** surface 6 got a `headers: Accept: json` + `text_absent` but NO `request:true` —
>   `page.goto` silently drops headers, so both runs still fetched HTML and passed vacuously. The
>   "JSON also not discriminating / gate on both layers, Final" verdict was a **harness bug**, not
>   a real gate (§6.15).  
> **Run 12:** harness gains a real **API-request mode** (`request:true` → APIRequestContext + raw-body
>   match). Double-run: **master FAILs** (JSON has `issue_badges`) / **badges-rm PASSes** (filtered) →
>   **surface 6 is the 3rd proven discriminator.** Full badges-rm checklist 7/7 green.  
> Checklist: 7 surfaces. **3 discriminators proven (1 + 6 + 7/old-9).**
> **Canonical final state + reusable lessons: see §7 and the skill's SKILL.md.**
> Historical run tables below use the original 9-surface numbering; §7 maps it to the committed 7-surface checklist.

---

## 1. Setup

```bash
# DEVSTACK_WORKSPACE is REQUIRED — docker-compose-pr.yml mounts ${DEVSTACK_WORKSPACE}/src:/edx/src
# (themes ship under it at /edx/src/themes). Unset → resolves to host /src (empty) → LMS boots with
# OSError: /edx/src/themes/ (§6.12, Issue #16). No separate themes mount needed.
export DEVSTACK_WORKSPACE=/Users/noahwang/workspace/hawthorn
export PLATFORM_MOUNT=/Users/noahwang/workspace/hawthorn/platform-badges-removal
docker compose -f docker-compose.yml -f docker-compose-pr.yml up -d lms studio
git checkout -- lms/envs/devstack_docker.py cms/envs/devstack_docker.py   # in the PR worktree
bash scripts/enable_devstack.sh      # from the skill dir; sets ENABLE_OPENBADGES etc. + restarts
bash scripts/provision-fixtures.sh   # Registration + staff/superuser for edx
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
| 9 | master | Baseline — surface 6 false gate (HTML artifact) | §6.14 |
| 10 | badges-rm | Surface 6 `headers` added but no `request:true` (still HTML) | 7/7 (vacuous) |
| 11 | master | Same — page.goto drops headers → HTML → false "gate" | §6.15 |
| 12 | master + badges-rm | Harness `request:true` (APIRequestContext, raw body) | **surface 6 discriminates: master FAIL / badges-rm PASS; 7/7** |

---

## 3. Discriminators

### Proven (measured on both branches)

| # | Surface | Layer | Master | badges-rm | Status |
|---|---------|-------|:---:|:---:|--------|
| 1 | `/api/badges/v1/assertions/user/{user}/` | URL routing | 200 | 404 | ✅ **proven** |
| 6 | `/settings/advanced/{course}` JSON `issue_badges` key (`request:true`) | CMS settings (`CourseMetadata.fetch`) | present | absent | ✅ **proven (Run 12)** — env-gated on `ENABLE_OPENBADGES` (§6.14/§6.15) |
| 9 | `/triboo-guanli/badges/badgeclass/` | Admin routing | 302 | 404 | ✅ **proven** — env-dependent (§6.10) |

### Candidate / Pending (NOT yet proven)

| # | Surface | Layer | Master | badges-rm | Blocker |
|---|---------|-------|:---:|:---:|--------|
| 3 | `accomplishments_shared` value | serializer | `true` | `false` | current assertion is gate only. Upgrade to value + re-baseline (§6.5) |

**Proven count: 3 (surfaces 1 + 6 + 9).**

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
| 14 | Surface 6 "gate" is a false verdict — `text_absent: badges` on Studio advanced settings | **Wrong assertion layer (§6.14).** Page is CodeMirror + async Backbone fetch; `body.innerText()` empty at assert → passes on both branches. Layer DOES discriminate: retarget to `/settings/advanced/{course}` **JSON**, assert `issue_badges` key present(master)/absent(badges-rm). |
| 15 | Retarget added `headers: Accept: json` but surface still vacuous (Run 10/11) | **`page.goto` ignores the `headers` option** (only `timeout`/`waitUntil`/`referer`) → request went out `Accept: text/html` → HTML again → innerText empty → false "gate on both layers". **Fixed:** harness gains `request:true` mode (APIRequestContext, honors headers + shares cookies, matches RAW body). Surface 6 then discriminates (Run 12). page-mode now throws if a surface sets headers, to prevent silent drops. (§6.15) |
| 16 | LMS `OSError: /edx/src/themes/` after PR remount | **`DEVSTACK_WORKSPACE` was unset** → `${DEVSTACK_WORKSPACE}/src` resolved to host `/src` (empty) → `/edx/src` empty → no themes. Export `DEVSTACK_WORKSPACE=<workspace-root>` (and `PLATFORM_MOUNT`) before `docker compose ... up`. Setup block updated. |

---

## 5. Next Steps (handoff — actionable)

### ✅ Done (Run 12) — surface 6 promoted to 3rd discriminator

- Harness `request:true` API mode added (`lib/checklist.ts` + `tests/checklist.spec.ts`); page mode
  now throws on stray `headers`. Surface 6 in `pr-2323.yml` set to `request:true` (§6.15).
- Double-run confirmed: master FAIL (`issue_badges` present) / badges-rm PASS (absent). Full 7/7 green.
- Lessons ported to `SKILL.md` (Hard-won rules 5 corrected + 6/8 added: shared LMS↔CMS session,
  `page.goto` drops headers → use `request:true` + raw body, set `DEVSTACK_WORKSPACE`).

### Backlog

1. ✅ All env corrections — surfaces 1, 4, 5 green on badges-rm.
2. ✅ Master baseline — surfaces 1 + 9 double-proven.
3. ✅ Surface 2 deleted (flaky+vacuous).
4. ✅ `docker-compose-pr.yml` mount fix — added `/edx/src`, removed the redundant `src/themes` overlay (§6.12).
5. ⚠️ Surface 3: upgrade gate to value assertion + re-baseline both branches.
6. ✅ Studio auth fixed at root (§6.1/§6.13) — `autoAuth` staff/superuser + shared session → both Studio surfaces green (Run 8). ⚠️ Surface 6's master baseline (Run 9) exposed a false "gate" — retarget HTML→JSON (§6.14, see top-of-section handoff).
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

### 6.14 Surface 6 — "gate" verdict is false; retarget HTML→JSON for a 3rd discriminator

Run 9 marked surface 6 a gate because `text_absent: badges` passed on master too. That is an
**assertion-layer artifact, not proof the layer is untestable.** Evidence (measured live):

- **Mount check:** the Run-9 container was on **master** (`git HEAD 8db868ed589`), not badges-rm —
  the setup block's `PLATFORM_MOUNT=.../platform-badges-removal` was overridden for the baseline.
- **Flag is effective:** CMS `settings.FEATURES['ENABLE_OPENBADGES'] == True`
  (`cms/envs/devstack_docker.py:44`), so on master `issue_badges` is **not** filtered out.
- **Assertion can't see it:** Studio advanced settings render via CodeMirror + an async Backbone
  model fetch; `page.locator('body').innerText()` is empty/incomplete at assert time → `text_absent`
  passes on **both** branches (doubly vacuous).
- **The layer DOES discriminate.** `git diff master..badges-removal cms/.../course_metadata.py`:
  badges-rm **adds `issue_badges` to the always-filtered list** and **removes** the old
  `ENABLE_OPENBADGES`-conditional filter. The `issue_badges` Boolean CourseField itself is retained
  on `course_module.py:503` in *both* branches (MongoDB back-compat) — so asserting the field
  definition is useless; assert whether it is **exposed in advanced settings**.

| | master (`ENABLE_OPENBADGES=True`) | badges-removal |
|---|:---:|:---:|
| `GET /settings/advanced/{course}` JSON contains `issue_badges` | **yes** (measured: HTTP 200 `application/json`, key present) | **no** (code-proven: always-filtered) |

**Fix:** retarget surface 6 to `GET :18010/settings/advanced/{course}` with `Accept: application/json`,
assert `issue_badges` **absent** on badges-rm / **present** on master. Env-dependency: requires CMS
`ENABLE_OPENBADGES=True` (else master hides it too → vacuous) — annotate like surfaces 7/9.
Reusable lesson (→ `SKILL.md`): **JS-rendered settings/admin pages (CodeMirror, async Backbone) are
unreliable for `innerText` assertions — assert the JSON/API layer instead.**
**→ RESOLVED in §6.15 (Run 12): surface 6 is now a proven discriminator.**

### 6.15 Surface 6 — resolved: `request:true` API mode makes it the 3rd discriminator (Run 12)

The §6.14 retarget alone was **not enough** — Run 10/11 added `headers: {Accept: application/json}`
but the surface stayed vacuous. Root cause: **Playwright `page.goto(url, {headers})` silently ignores
`headers`** (valid options are only `timeout`/`waitUntil`/`referer`; extra headers need
`setExtraHTTPHeaders` or the APIRequestContext). So the request still went out `Accept: text/html`,
Django returned the HTML editor page, and `body.innerText()` was empty → `text_absent` passed on both
branches ⇒ the "JSON also not discriminating / gate on both layers, **Final**" conclusion was a
harness bug, not a real gate.

**Fix (harness):** `lib/checklist.ts` + `tests/checklist.spec.ts` gain a `request: true` mode —
the runner fetches via `ctx.request.get(url, {headers})` (Playwright APIRequestContext: shares the
context cookie jar AND honors `headers`) and asserts the **raw response body**, never `innerText`.
Page mode now **throws** if a surface declares `headers` (so a header-dependent surface can never
silently pass again). `checklists/pr-2323.yml` surface 6 set to `request: true`.

**Double-run (Run 12), measured live:**

| branch | `GET :18010/settings/advanced/{course}` (`Accept: json`) | surface 6 (`text_absent: issue_badges`) |
|--------|:---:|:---:|
| master (`ENABLE_OPENBADGES=True`) | JSON contains `issue_badges` | ❌ FAIL (correctly detects it's present) |
| badges-rm | `issue_badges` filtered out | ✅ PASS |

Full badges-rm checklist re-run: **7/7 green**. Surface 6 is now the **3rd proven discriminator**
(CMS-settings layer), env-gated on `ENABLE_OPENBADGES`.

Two reusable lessons (now in `SKILL.md`, Hard-won rule 6):
`page.goto` drops a `headers` option; and API/JSON assertions must target the **raw response body**,
not `innerText` (which only sees visible rendered text).

### 6.7 Priority order
1. ✅ Surfaces 1 + 6 + 9 double-proven (3 discriminators).
2. ✅ Studio auth — shared LMS↔CMS session + staff/superuser (§6.1/§6.13).
3. ⚠️ Surface 3 value assertion upgrade (`accomplishments_shared` true→false, §6.5).
4. Split surface 5 (share buttons gate vs OpenBadges half, §6.6).
5. Apply the harness (+ `request:true` pattern) to #2322/#2324/#2348.

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
| 6 | Studio advanced settings (`request:true` JSON) | ✅ **discriminator** | proven Run 12 (§6.15): `issue_badges` in JSON present(master)/absent(badges-rm); env-gated on `ENABLE_OPENBADGES` |
| 7 | admin `/triboo-guanli/badges/badgeclass/` | ✅ **discriminator** | env-gated on `ENABLE_DJANGO_ADMIN_SITE` (§6.10); non-404→404 |

**Reusable lessons** (discriminator-vs-gate, double-run every retarget, fork-relocated
/ env-gated URLs, **shared LMS↔CMS session — staff/superuser is the real Studio gate**,
**`page.goto` drops headers → use `request:true` + assert raw body, never `innerText`**,
reset polluted `devstack_docker.py`, set `DEVSTACK_WORKSPACE` for the PR mount) now live
in the skill's `SKILL.md` → *Hard-won rules*, so they travel with the skill to other
removal PRs. This log stays as the #2323-specific run evidence.

### Cross-artifact correspondence (verify before merging either side)

| Artifact | Repo / branch | Carries |
|----------|---------------|---------|
| `SKILL.md`, `checklists/pr-2323.yml`, `lib/checklist.ts`, `tests/checklist.spec.ts`, `lib/auth.ts` | platform / `browser-acceptance-harness` (HEAD `540e34505cd` **+ uncommitted Run-12 changes**: `request:true` mode, surface 6, SKILL.md rules) | assertions + auth + API-request mode + reusable rules |
| `docker-compose-pr.yml`, `verify-pr.sh`, this log | devstack / `noah-py2-m-chip-master` (commit `c44320c`, **+ uncommitted** this log) | infra + run evidence |
| PR under test | platform / `badges-removal` | #2323 |
