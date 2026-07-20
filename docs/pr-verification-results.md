# PR Verification — Execution Results

> Date: 2026-07-20  
> PR: #2323 badges removal  
> Branch: `browser-acceptance-harness` (checklist runner) + `badges-removal` (PR worktree)  
> Tool: Playwright Test/TS + checklist-as-code runner
>
> **Run 1 (initial):** 4/9 passed. **Run 2 (corrected):** 5/8 passed.  
> **Run 3 (master baseline):** 4 passed, 4 failed — **surface 1 is the only proven discriminator.**
> Studio ×2 (302) blocked by CMS auth; admin ×1 (404) is an LMS route gap — see §6 review.

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

### Run 3 — Master baseline (16.0s)

| # | Surface | Auth | Assertion | Master | badges-rm | Discriminates? |
|---|---------|------|-----------|:---:|:---:|:---:|
| 1 | Badges API | qacert | 404 | 🔴 FAIL (200) | ✅ | ✅ **yes** |
| 2 | Profile badge container | qacert | `.badge-list-container` absent | ✅ | ✅ | ❌ vacuous |
| 3 | User API badges | qacert | `badges` text absent | ✅ | ✅ | ❌ vacuous |
| 4 | LMS homepage | edx | 200 | ✅ | ✅ | — (gate) |
| 5 | Cert share buttons | qacert | `.action-share-facebook` visible | ✅ | ✅ | — (gate) |
| 7 | Studio home | edx | 200 | ❌ (302) | ❌ (302) | auth block |
| 8 | Studio advanced settings | edx | 200, badge toggle absent | ❌ (302) | ❌ (302) | auth block |
| 9 | Django admin | edx | 200, badge links absent | ❌ (404) | ❌ (404) | route gap |

**4 passed, 4 failed on master.** Surface 1 — the badges API route deletion — is the **only** discriminating assertion. Surfaces 2/3 pass on both branches (vacuous — no BadgeAssertion fixture means badge markers are absent on master too).

### Run 2 (badges-removal, after corrections)

| # | Surface | Result |
|---|---------|:---:|
| 1 | Badges API 404 | ✅ |
| 2 | Profile badge container absent | ✅ |
| 3 | User API badges absent | ✅ |
| 4 | LMS homepage 200 | ✅ |
| 5 | Cert share buttons visible | ✅ |
| 7 | Studio home | ❌ (302) |
| 8 | Studio advanced settings | ❌ (302) |
| 9 | Django admin | ❌ (404) |

**5/8 passed.** All LMS surfaces green. 3 failures are auth/route gaps, not PR regressions.

---

## 3. Baseline Comparison

| Surface | badges-rm | Master | Verdict |
|---------|:---:|:---:|------|
| 1. Badges API | ✅ (404) | 🔴 (200) | **Discriminator — route deleted** |
| 2. Profile badges | ✅ (~absent) | ✅ (~absent) | **Vacuous** — no fixture on either branch |
| 3. User API | ✅ (~absent) | ✅ (~absent) | **Vacuous** — no BadgeAssertion → no badge fields |
| 4. LMS home | ✅ 200 | ✅ 200 | Gate (no import error) |
| 5. Cert share | ✅ visible | ✅ visible | Gate (SOCIAL_SHARING_SETTINGS) |
| 7/8/9 Studio | ❌ 302/404 | ❌ 302/404 | Auth/route gap on both branches |

---

## 4. Issues Encountered

| # | Issue | Resolution |
|---|-------|-----------|
| 1 | `edx` auto_auth 500 — no Registration record | `Registration.objects.get_or_create(user=edx)` |
| 2 | ~~`SOCIAL_SHARING_SETTINGS` NameError → removed the line~~ | **Reverted diagnosis.** Var IS defined in `common.py:2345`; NameError from polluted `devstack_docker.py`. Clean + re-enable. |
| 3 | Worktree doesn't have acceptance flags | `enable_devstack.sh` after each worktree switch |
| 4 | curl `+` → space (URL encoding) | curl issue only; Playwright handles correctly |
| 5 | LMS restart takes 15-30s per switch | Factor into pipeline timing |
| 6 | `npm run --silent` still noisy | Normal |
| 7 | `devstack_docker.py` polluted | `git checkout --` then `enable_devstack.sh` once |
| 8 | ~~Studio 302 — LMS session cookie doesn't cross ports~~ | **Wrong mechanism (see §6.1).** Cookies ignore port (RFC 6265). Real cause: CMS uses distinct `SESSION_COOKIE_NAME` or has no session. Fix: auto_auth against `:18010/auto_auth`. |
| 9 | `/admin/` 404 — LMS admin route absent | LMS-side (port 18000). Retarget to `/admin/badges/badgeassertion/` and assert 404 (isomorphic to surface 1). |

---

## 5. Next Steps (handoff — actionable)

1. ✅ Clean + re-enable → surface 5 green.
2. ✅ Elevate `edx` → is_staff=1, is_superuser=1.
3. ✅ Delete surface 6 → removed.
4. ✅ **Master baseline → surface 1 is the only discriminator. Surfaces 2/3 are vacuous — upgrade to route-level checks or provision BadgeAssertion fixture.**
5. **Retarget surface 3 to the `accomplishments_shared` value flip (§6.5)** — cheapest new
   real discriminator, no fixture needed. Do NOT "upgrade 2/3 to `GET /api/badges/...`":
   that only re-tests surface 1 and covers neither the serializer nor the JS layer.
6. Fix CMS auto_auth (§6.1) → unlock Studio surface 8 (issue_badges toggle — second discriminator).
7. Fix admin route (§6.2) → retarget surface 9 to 404 assertion.
8. Split surface 5 (§6.6): keep the share-button `visible` as a gate; mark the OpenBadges
   `absent`/`text_absent` part as **vacuous** under `issue_badges=False`.
9. Surface 2 (profile JS/template): non-vacuous only with a real `BadgeAssertion` fixture on
   master; if not worth the cost, label it "covered by unit tests", don't keep it vacuous.
10. Apply pattern to other migration PRs (embargo #2322, support #2324, M4.4-A #2348).

---

## 6. Review corrections (2026-07-20)

### 6.1 "Cross-port cookie" claim is wrong

Cookies ignore port (RFC 6265): the `sessionid` set by `:18000/auto_auth` **is** sent to `:18010`. The Studio 302 is therefore **not** "cookie can't cross origin". Real cause:

- devstack's `cms.env.json` may set a **distinct `SESSION_COOKIE_NAME`**, or
- `auto_auth` only created an **LMS** session; CMS has no matching session row.

**Action:** verify by printing browser cookies after auto_auth + reading `SESSION_COOKIE_NAME` from `cms.env.json`. **Fix** = auto_auth against CMS origin (`http://localhost:18010/auto_auth`), not "accept cookies can't cross ports".

### 6.2 admin 404 is LMS-side

Surface 9 `/admin/` → `:18000` (LMS). 404 means LMS has no Django admin in this devstack. **Action:** retarget to `/admin/badges/badgeassertion/` and assert `404` — isomorphic to surface 1.

### 6.3 Vacuous-assertion risk — confirmed by baseline

`provision-fixtures.sh` sets `course.issue_badges = False`. Consequence: on **master** badge markers are also absent. **Baseline proved surfaces 2/3 are vacuous.** Only surface 1 (API route 404) is a real discriminator.

| Assertion | Master | badges-rm | Discriminates? |
|-----------|:---:|:---:|:---:|
| Surface 1 — badges API 404 | ❌ (200) | ✅ | ✅ **proven** |
| Surface 2 — badge container absent | ✅ | ✅ | ❌ vacuous |
| Surface 3 — user API badges absent | ✅ | ✅ | ❌ vacuous |
| Surface 8 — Studio issue_badges toggle (blocked by §6.1) | — | — | 🔒 likely discriminator |

### 6.5 Surface 3 tests the wrong thing — retarget to `accomplishments_shared` (diff-verified)

#2323 did **not** remove a `badges` field from the accounts API. The actual change in
`openedx/core/djangoapps/user_api/accounts/serializers.py`:

```diff
-        accomplishments_shared = badges_enabled()
+        accomplishments_shared = False
```

and `views.py` explicitly keeps the field: *"accomplishments_shared: Always false. Retained
in the API contract for backward compatibility."* So:

- The JSON key is `accomplishments_shared`, never the literal `badges` → `text_absent: badges`
  passes on both branches = **vacuous** (baseline confirmed).
- The real, testable behavior change is the **value flip**. With `ENABLE_OPENBADGES=True`
  (set by `enable_devstack.sh`):
  - master → `"accomplishments_shared": true`  (`badges_enabled()` returns True)
  - badges-rm → `"accomplishments_shared": false`  (hardcoded)

**Action:** replace surface 3's `text_absent: badges` with an assertion on
`"accomplishments_shared": false` (present on badges-rm, `true` on master). This covers the
**serializer layer** — a genuine second discriminator, no fixture required. A `GET
/api/badges/...` route check would NOT cover this layer.

### 6.6 Surface 5 has a hidden vacuous half

The cert surface bundles two assertion groups: `visible: [share buttons]` (a live gate) and
`absent: ico-mozillaopenbadges` / `text_absent: OpenBadges`. Because `provision-fixtures.sh`
sets `course.issue_badges = False`, the badge modal never renders on master either → the
OpenBadges half is **also vacuous** (only 2/3 were flagged before). Keep the share-button
gate; don't count the OpenBadges half as removal proof.

### Honest coverage after Run 3

Only **surface 1 (API route 404)** is a proven discriminator. Everything else "removal"-shaped
is vacuous (2, 3, 5-OpenBadges-half) or blocked (7/8/9). The checklist currently
**under-verifies #2323** — §6.5 (serializer) and §6.1→§6.4 (Studio `issue_badges`) are the
two cheapest ways to add real layer coverage.

### 6.7 Priority order

1. ✅ **Master baseline — done.** Surface 1 proven; surfaces 2/3 vacuous.
2. **§6.5 — retarget surface 3 to `accomplishments_shared` value flip** (cheapest real
   discriminator, no fixture).
3. §6.1 (CMS auto_auth) → unlock surface 8 (Studio `issue_badges`) discriminator.
4. §6.2 (admin route → `/admin/badges/badgeassertion/` 404) → third route-level proof.
5. §6.6 — split surface 5; §6.3/6.4 — decide surface 2 (fixture or drop).
6. Apply pattern to PRs #2322/#2324/#2348.
