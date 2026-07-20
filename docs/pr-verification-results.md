# PR Verification — Execution Results

> Date: 2026-07-20  
> PR: #2323 badges removal  
> Branch: `browser-acceptance-harness` (checklist runner) + `badges-removal` (PR worktree)  
> Tool: Playwright Test/TS + checklist-as-code runner
>
> **Run 1:** 4/9. **Run 2:** 5/8. **Run 3:** master baseline, surface 1 discriminator.  
> **Run 4:** 6/8 (surface 3 retarget + admin 404 — but admin false positive, §6.8).  
> **Run 5:** Master baseline with corrected `/triboo-guanli/` URL — **2 discriminators proven (surfaces 1 + 9).**  
> **Run 6:** badges-rm final — surface 2 deleted (flaky+vacuous), 5/7 passed. Themes mount fix applied.  
> Checklist: 7 surfaces. 2 discriminators. 2 Studio blocked (CMS auth §6.1). 1 gate candidate (surface 3).

---

## 1. Setup

```bash
export PLATFORM_MOUNT=/Users/noahwang/workspace/hawthorn/platform-badges-removal
docker compose -f docker-compose.yml -f docker-compose-pr.yml up -d lms studio
git checkout -- lms/envs/devstack_docker.py cms/envs/devstack_docker.py
bash scripts/enable_devstack.sh
bash scripts/provision-fixtures.sh
# Registration + superuser for edx
# Note: docker-compose-pr.yml requires themes mount (added Run 6)
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
| 6 | badges-rm | Surface 2 deleted + themes fix | 5/7 (stable) |

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
| 8 | Studio `issue_badges` toggle | CMS settings | present | absent | CMS auth (§6.1) |

**Proven count: 2 (surfaces 1 + 9).**

---

## 4. Issues Encountered

| # | Issue | Resolution |
|---|-------|-----------|
| 1 | `edx` auto_auth 500 — no Registration | `Registration.objects.get_or_create(user=edx)` |
| 2 | `SOCIAL_SHARING_SETTINGS` misdiagnosis | Var IS defined; polluted `devstack_docker.py`. Clean + re-enable. |
| 3 | Worktree flags | `enable_devstack.sh` after each switch |
| 7 | `devstack_docker.py` polluted | `git checkout --` then `enable_devstack.sh` once |
| 8 | Studio 302 — not "cross-port cookie" | CMS distinct `SESSION_COOKIE_NAME`. Fix: auto_auth on `:18010` |
| 9 | Admin at wrong URL | **FIXED:** `/triboo-guanli/badges/badgeclass/` ✅ |
| 10 | Surface 3 gate, not discriminator | Upgrade to value assertion (§6.5) |
| 11 | `docker-compose-pr.yml` missing themes mount | **FIXED Run 6.** Added `${DEVSTACK_WORKSPACE}/src/themes:/edx/src/themes:cached` for both lms + studio. Without it, PR worktree switch → OSError on theme dir. |
| 12 | Surface 2 flaky + vacuous | **DELETED Run 6.** No BadgeAssertion fixture + page timeout on master. |

---

## 5. Next Steps (handoff — actionable)

1. ✅ All env corrections — surfaces 1, 4, 5 green on badges-rm.
2. ✅ Master baseline — surfaces 1 + 9 double-proven.
3. ✅ Surface 2 deleted (flaky+vacuous).
4. ✅ Themes mount fix (`docker-compose-pr.yml`).
5. ⚠️ Surface 3: upgrade gate to value assertion + re-baseline both branches.
6. 🔒 CMS auto_auth (§6.1) → surface 8.
7. §6.10 — gate surface 9 on `ENABLE_DJANGO_ADMIN_SITE`.
8. §6.6 — split surface 5 OpenBadges half.
9. Apply to PRs #2322/#2324/#2348.

---

## 6. Review corrections

### 6.1 Studio 302 — not cross-port cookie
CMS uses distinct `SESSION_COOKIE_NAME`. Fix: auto_auth against `http://localhost:18010/auto_auth`.

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

### 6.7 Priority order
1. ✅ Surface 1 + 9 double-proven.
2. ⚠️ Surface 3 value assertion upgrade.
3. 🔒 CMS auto_auth → surface 8.
4. Split surface 5.
5. Apply to #2322/#2324/#2348.
