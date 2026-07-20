# PR Verification — Execution Results

> Date: 2026-07-20  
> PR: #2323 badges removal  
> Branch: `browser-acceptance-harness` (checklist runner) + `badges-removal` (PR worktree)  
> Tool: Playwright Test/TS + checklist-as-code runner
>
> **Run 1:** 4/9. **Run 2:** 5/8. **Run 3:** master baseline, surface 1 discriminator.  
> **Run 4:** 6/8 (surface 3 retarget + admin 404 — but admin false positive, §6.8).  
> **Run 5:** Master baseline with corrected `/triboo-guanli/` URL — **2 discriminators proven (surfaces 1 + 9).**  
> Studio ×2 (302/403) blocked by CMS auth (§6.1). Surface 3 is a gate (value assertion upgrade pending, §6.5).

---

## 1. Setup

```bash
export PLATFORM_MOUNT=/Users/noahwang/workspace/hawthorn/platform-badges-removal
docker compose -f docker-compose.yml -f docker-compose-pr.yml up -d lms studio
git checkout -- lms/envs/devstack_docker.py cms/envs/devstack_docker.py
bash scripts/enable_devstack.sh
bash scripts/provision-fixtures.sh
# Registration + superuser for edx
# Run: BROWSER_ACCEPTANCE_BASE_URL=http://localhost:18000 CHECKLIST_PR=pr-2323 npm run checklist
```

---

## 2. Results

### Run 5 — Master baseline with corrected `/triboo-guanli/` URL (45.8s)

| # | Surface | Master | badges-rm | Discriminates? |
|---|---------|:---:|:---:|:---:|
| 1 | Badges API `/api/badges/v1/...` | 🔴 200 (FAIL) | ✅ 404 | ✅ **proven** |
| 9 | Admin `/triboo-guanli/badges/badgeclass/` | 🔴 302 (FAIL) | ✅ 404 | ✅ **proven** |
| 2 | Profile badge container | ✅ absent | ✅ absent | ❌ vacuous |
| 3 | User API — accomplishments_shared gate | ✅ present | ✅ present | ⚠️ gate (value assertion pending) |
| 7/8 | Studio surfaces | ❌ 302/403 | ❌ 302/403 | auth block (§6.1) |

**Run 5 master baseline: 3 passed, 4 failed, 1 flaky (surfaces 2 timeout).**

### Run 4 — badges-removal (11.6s)

| # | Surface | Result |
|---|---------|:---:|
| 1 | Badges API 404 | ✅ |
| 2 | Profile badge container | ✅ |
| 3 | User API — accomplishments_shared | ✅ |
| 4 | LMS homepage 200 | ✅ |
| 5 | Cert share buttons | ✅ |
| 7 | Studio home | ❌ (302) |
| 8 | Studio advanced settings | ❌ (302) |
| 9 | Admin badges 404 | ✅ |

**6/8 passed on badges-removal.**

### Run progression

| Run | Branch | Change | Result |
|:---:|--------|--------|:---:|
| 1 | badges-rm | Initial | 4/9 |
| 2 | badges-rm | env corrections | 5/8 |
| 3 | master | Baseline (old surface 3/9) | 1 discriminator found |
| 4 | badges-rm | Surface 3 retarget + admin URL | 6/8 |
| 5 | master | Corrected `/triboo-guanli/` URL | **2 discriminators proven** |

---

## 3. Discriminators

### Proven (measured on both branches)

| # | Surface | Layer | Master | badges-rm | Status |
|---|---------|-------|:---:|:---:|--------|
| 1 | `/api/badges/v1/assertions/user/{user}/` | URL routing | 200 | 404 | ✅ **proven** |
| 9 | `/triboo-guanli/badges/badgeclass/` | Admin routing | 302 | 404 | ✅ **proven** — but see §6.10 (env-dependent; gate on `ENABLE_DJANGO_ADMIN_SITE`) |

### Candidate / Pending (NOT yet proven — expected values are from the diff, not measured)

| # | Surface | Layer | Master (expected) | badges-rm (expected) | Blocker |
|---|---------|-------|:---:|:---:|--------|
| 3 | `accomplishments_shared` **value** | serializer | `true` | `false` | current assertion only checks field **presence** (gate, passes both). Upgrade to value assertion + re-baseline (§6.5). Needs auto_auth. |
| 8 | Studio `issue_badges` toggle | CMS settings | present | absent | CMS auth (§6.1) — surface never executed. |

**Proven discriminator count: 2 (surfaces 1 + 9). Surfaces 3 and 8 are candidates, not proof.**

---

## 4. Issues Encountered

| # | Issue | Resolution |
|---|-------|-----------|
| 1 | `edx` auto_auth 500 — no Registration | `Registration.objects.get_or_create(user=edx)` |
| 2 | `SOCIAL_SHARING_SETTINGS` misdiagnosis | Var IS defined; polluted `devstack_docker.py`. Clean + re-enable. |
| 3 | Worktree flags | `enable_devstack.sh` after each switch |
| 7 | `devstack_docker.py` polluted | `git checkout --` then `enable_devstack.sh` once |
| 8 | Studio 302 — not "cross-port cookie" | Real cause: CMS distinct `SESSION_COOKIE_NAME`. Fix: auto_auth on `:18010` |
| 9 | Admin at wrong URL (§6.8) | **FIXED:** retarget to `/triboo-guanli/badges/badgeclass/`. Master returns 302, badges-rm returns 404. ✅ |
| 10 | Surface 3 gate, not discriminator | Upgrade to value assertion (§6.5). |

---

## 5. Next Steps (handoff — actionable)

1. ✅ All env corrections — surfaces 1, 4, 5 green on badges-rm.
2. ✅ Master baseline with corrected URLs — surfaces 1 + 9 double-proven.
3. ⚠️ Surface 3: upgrade gate to value assertion (`"accomplishments_shared": false` vs `true`) + re-baseline both branches.
4. 🔒 Fix CMS auto_auth (§6.1) → unlock surface 8 (Studio issue_badges — highest remaining discriminator).
5. §6.6 — split surface 5: keep share-button gate; mark OpenBadges half vacuous.
6. Surface 2: vacuous **and** flaky (timed out on the Run-5 master baseline). Drop it, or label
   "covered by unit tests" / provision a real BadgeAssertion. Don't keep a vacuous+flaky case.
7. §6.10 — gate surface 9 on `ENABLE_DJANGO_ADMIN_SITE` so it degrades loudly (not to a silent
   404-on-both) if admin is disabled in another environment.
8. Apply pattern to PRs #2322/#2324/#2348.

---

## 6. Review corrections

### 6.1 Studio 302 — not cross-port cookie
CMS uses distinct `SESSION_COOKIE_NAME`. Fix: auto_auth against `http://localhost:18010/auto_auth`.

### 6.5 Surface 3 — upgrade to value assertion
Diff: `accomplishments_shared = badges_enabled()` → `= False`. Current assertion `text_present: accomplishments_shared` is a gate (passes on both). To discriminate: assert the VALUE — `"accomplishments_shared": false` (badges-rm) vs `true` (master). Requires auto_auth (API returns 403 without session).

### 6.6 Surface 5 vacuous half
Cert bundles: share buttons (live gate) + OpenBadges absent (vacuous under `issue_badges=False`).

### 6.8 Admin URL — FIXED in Run 5
Triboo fork moves admin to `/triboo-guanli/`. Original `/admin/` URL was 404 on both branches. Corrected to `/triboo-guanli/badges/badgeclass/` — master returns 302, badges-rm returns 404. Proved with double-run baseline. ✅

### 6.9 Process rule
Every retarget must be re-run on BOTH master and badges-rm. Single-branch "proven" claims are void.

### 6.10 Surface 9 is env-dependent — gate it on `ENABLE_DJANGO_ADMIN_SITE`
Admin is routed only when `settings.DEBUG or FEATURES['ENABLE_DJANGO_ADMIN_SITE']` (see
`lms/urls.py`). Run 5's 302-vs-404 flip only holds because admin is enabled in THIS devstack.
In an environment where admin is off, `/triboo-guanli/...` is 404 on **both** branches →
surface 9 silently becomes vacuous again (same failure class as §6.8). Add the flag as a
precondition (skip/xfail the surface when off) so it fails loudly instead of passing vacuously.

### 6.11 Run 5 verdict — accepted
Surface 9's 302→404 is a legitimate route-existence flip and is **auth-independent** (any
non-404 on master vs 404 on badges-rm discriminates). Combined with surface 1, **2 real
discriminators are proven.** Residual cleanups only: §6.10 (gate), §3 reclassification
(3/8 are candidates, not proven), and surface 2 (drop/relabel).

### 6.7 Priority order
1. ✅ Surface 1 + 9 double-proven (Run 5).
2. ⚠️ Surface 3 — upgrade to value assertion + double-baseline.
3. 🔒 CMS auto_auth → surface 8.
4. Split surface 5; decide surface 2.
5. Apply to #2322/#2324/#2348.
