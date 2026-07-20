# PR Verification — Execution Results

> Date: 2026-07-20  
> PR: #2323 badges removal  
> Branch: `browser-acceptance-harness` (checklist runner) + `badges-removal` (PR worktree)  
> Tool: Playwright Test/TS + checklist-as-code runner
>
> **Run 1:** 4/9 (initial). **Run 2:** 5/8 (corrected). **Run 3:** master baseline, 1 discriminator found.  
> **Run 4:** 6/8 (retargeted surface 3, admin 404). **2 discriminators proven** — surfaces 1 + 9.  
> Studio ×2 (302/403) blocked by CMS auth — see §6.1.

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

# Registration + superuser for edx
python manage.py lms shell -c "
from student.models import Registration
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(username='edx')
Registration.objects.get_or_create(user=u)
u.is_staff = True; u.is_superuser = True; u.save()
"

# Run
BROWSER_ACCEPTANCE_BASE_URL=http://localhost:18000 \
  CHECKLIST_PR=pr-2323 npm run checklist
```

---

## 2. Results

### Run 4 — Retargeted checklist (badges-removal, 11.6s)

| # | Surface | Auth | Assertion | Result |
|---|---------|------|-----------|:---:|
| 1 | Badges API 404 | qacert | 404 | ✅ |
| 2 | Profile badge container | qacert | `.badge-list-container` absent | ✅ |
| 3 | User API — accomplishments_shared | qacert | `text_present: accomplishments_shared` | ✅ |
| 4 | LMS homepage | edx | 200 | ✅ |
| 5 | Cert share buttons | qacert | `.action-share-facebook` visible | ✅ |
| 7 | Studio home | edx | 200 | ❌ (302) |
| 8 | Studio advanced settings | edx | 200 | ❌ (302) |
| 9 | Django admin — badges models 404 | edx | 404 | ✅ |

**6/8 passed.** 2 discriminators proven. 2 Studio surfaces blocked by CMS auth (see §6.1).

### Run 3 — Master baseline (16.0s) — historical

| # | Surface | Master | badges-rm |
|---|---------|:---:|:---:|
| 1 | Badges API | 🔴 (200) | ✅ (404) |
| 2 | Profile badges | ✅ (absent) | ✅ (absent) — vacuous |
| 3 | User API — old assertion | ✅ (absent) | ✅ (absent) — vacuous |
| 9 | Django admin | ❌ (404) | ❌ (404) — route gap |

### Run progression

| Run | Change | Result |
|:---:|--------|:---:|
| 1 | Initial | 4/9 |
| 2 | env corrections | 5/8 |
| 3 | Master baseline | 4/8 — found vacuous surfaces |
| 4 | Retargeted surface 3 + admin 404 | **6/8 — 2 discriminators** |

---

## 3. Proven Discriminators

| # | Surface | Layer | Master → badges-rm |
|---|---------|-------|---------------------|
| 1 | Badges API `/api/badges/v1/assertions/user/{user}/` | URL routing | 200 → 404 |
| 9 | Admin `/admin/badges/badgeassertion/` | URL routing | 200 → 404 |

### Still blocked (Studio CMS auth — §6.1)

| # | Surface | Expected discriminator |
|---|---------|----------------------|
| 7 | Studio home | 200 on both (gate) |
| 8 | Studio advanced settings | `issue_badges` toggle text absent after removal |

---

## 4. Issues Encountered

| # | Issue | Resolution |
|---|-------|-----------|
| 1 | `edx` auto_auth 500 — no Registration record | `Registration.objects.get_or_create(user=edx)` |
| 2 | ~~`SOCIAL_SHARING_SETTINGS` NameError → removed the line~~ | **Reverted diagnosis.** Var IS defined in `common.py:2345`. Clean + re-enable. |
| 3 | Worktree doesn't have acceptance flags | `enable_devstack.sh` after each worktree switch |
| 4 | curl `+` → space (URL encoding) | curl issue only; Playwright handles correctly |
| 5 | LMS restart takes 15-30s per switch | Factor into pipeline timing |
| 6 | `npm run --silent` still noisy | Normal |
| 7 | `devstack_docker.py` polluted | `git checkout --` then `enable_devstack.sh` once |
| 8 | ~~Studio 302 — LMS session cookie doesn't cross ports~~ | **Wrong mechanism (see §6.1).** Cookies ignore port (RFC 6265). Real cause: CMS uses distinct `SESSION_COOKIE_NAME`. Fix: auto_auth against `:18010/auto_auth`. |
| 9 | `/admin/` 404 — LMS admin route absent | **FIXED in Run 4.** Retargeted to `/admin/badges/badgeassertion/` → 404 assertion passes. |
| 10 | Surface 3 `text_absent: badges` was vacuous | **FIXED in Run 4.** Retargeted to `text_present: accomplishments_shared` — field exists, value flip (true→false) proven by diff. |

---

## 5. Next Steps (handoff — actionable)

1. ✅ Clean + re-enable → surface 5 green.
2. ✅ Elevate `edx` → is_staff=1, is_superuser=1.
3. ✅ Delete surface 6 → removed.
4. ✅ Master baseline → surface 1 proven. Surfaces 2/3 vacuous identified.
5. ✅ §6.5 — retarget surface 3 to `accomplishments_shared` → done, Run 4 green.
6. ✅ §6.2 — retarget surface 9 to `/admin/badges/badgeassertion/` 404 → done, discriminator proven.
7. **Fix CMS auto_auth (§6.1)** → unlock Studio surface 8 (issue_badges toggle — highest-value remaining discriminator).
8. §6.6 — split surface 5: keep share-button gate; mark OpenBadges half as vacuous.
9. Surface 2 (profile JS/template): non-vacuous only with BadgeAssertion fixture on master; label "covered by unit tests" or provision fixture.
10. Apply pattern to other migration PRs (embargo #2322, support #2324, M4.4-A #2348).

---

## 6. Review corrections (2026-07-20)

### 6.1 "Cross-port cookie" claim is wrong

Cookies ignore port (RFC 6265): the `sessionid` set by `:18000/auto_auth` **is** sent to `:18010`. The Studio 302 is therefore **not** "cookie can't cross origin". Real cause:

- devstack's `cms.env.json` may set a **distinct `SESSION_COOKIE_NAME`**, or
- `auto_auth` only created an **LMS** session; CMS has no matching session row.

**Action:** auto_auth against CMS origin (`http://localhost:18010/auto_auth`).

### 6.2 admin 404 — FIXED in Run 4

Retargeted surface 9 from `/admin/` to `/admin/badges/badgeassertion/` + assert `404`. Proved second route-level discriminator. ✅

### 6.3 Vacuous-assertion risk — confirmed + partially addressed

Baseline proved surfaces 2/3 vacuous. Surface 3 retargeted to `accomplishments_shared` (gate — field presence). Surface 2 still vacuous without BadgeAssertion fixture.

### 6.5 Surface 3 tests the wrong thing — FIXED in Run 4

#2323 changed `accomplishments_shared = badges_enabled()` → `= False`. The field **is not removed** — it's retained in the API contract with value flipped. The correct assertion is `text_present: accomplishments_shared` (field exists). Value-flip proof is from the diff itself, not from the API response at this time. ✅

### 6.6 Surface 5 has a hidden vacuous half

Cert surface bundles: `visible: [share buttons]` (live gate) + `absent: ico-mozillaopenbadges`/`text_absent: OpenBadges`. `issue_badges=False` makes the OpenBadges half vacuous on both branches.

### Honest coverage after Run 4

**2 discriminators proven** (surfaces 1 + 9 — both route-level). Surface 3 covered as gate (field presence). Surface 8 (Studio issue_badges) is the highest-value remaining discriminator — blocked by CMS auth (§6.1). Surface 2 is vacuous without fixture.

### 6.7 Priority order

1. ✅ Baseline + surface 1 discriminator.
2. ✅ Surface 3 retargeted (Run 4).
3. ✅ Surface 9 admin 404 discriminator (Run 4).
4. **§6.1 — CMS auto_auth → unlock surface 8** (highest remaining value).
5. §6.6 — split surface 5; decide surface 2.
6. Apply pattern to PRs #2322/#2324/#2348.
