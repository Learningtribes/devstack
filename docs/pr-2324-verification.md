# PR #2324 Support + Zendesk Removal — Verification Results

> Date: 2026-07-21
> PR: #2324 support + zendesk removal (M4 DCC)
> Branch: `support-zendesk-removal` (worktree `platform-support-zendesk-removal`)
> Runner: Playwright checklist-as-code (`browser-acceptance-harness`)
> Checklist: `checklists/pr-2324.yml` — 7 surfaces

---

## 1. PR Summary

156 files changed, 219 insertions, 8802 deletions. Two modules removed.

| Module | Location | Content |
|--------|----------|---------|
| Support dashboard | `lms/djangoapps/support/` | Views, URLs, serializers, decorators, templates, Backbone JS + React JSX |
| Zendesk proxy | `openedx/core/djangoapps/zendesk_proxy/` | v0/v1 API views, settings, utils |

Key settings changes:
- `FEATURES['ENABLE_FEEDBACK_SUBMISSION']` removed from lms/cms common.py
- `ZENDESK_URL/USER/API_KEY/CUSTOM_FIELDS` removed
- `FINANCIAL_ASSISTANCE_MIN_LENGTH/MAX_LENGTH` removed
- `INSTALLED_APPS` → `support` app removed
- `lms/urls.py` → `^support/` route block removed, `submit_feedback` → `submit_support_form`

---

## 2. Results

### support-zendesk-removal — 7/7 passed (4.4s)

| # | Surface | Result |
|---|---------|:---:|
| 1 | `/support/` → 404 | ✅ |
| 2 | `/support/certificates/` → 404 | ✅ |
| 3 | `/support/enrollment/` → 404 | ✅ |
| 4 | `/support/contact_us/` → 404 | ✅ |
| 5 | LMS `/` → 200 | ✅ |
| 6 | `/submit_support_form` → 405 | ✅ |
| 7 | Studio `/home/` → 200 | ✅ |

### Master baseline — 3 passed, 4 failed

| # | Surface | Master | support-zendesk-rm | Role |
|---|---------|:---:|:---:|------|
| 1 | `/support/` | ❌ 200 | ✅ 404 | **discriminator** |
| 2 | `/support/certificates/` | ❌ 200 | ✅ 404 | **discriminator** |
| 3 | `/support/enrollment/` | ❌ 200 | ✅ 404 | **discriminator** |
| 4 | `/support/contact_us/` | ❌ 200 | ✅ 404 | **discriminator** |
| 5 | LMS `/` | ✅ 200 | ✅ 200 | gate |
| 6 | `/submit_support_form` | ✅ 405 | ✅ 405 | gate |
| 7 | Studio `/home/` | ✅ 200 | ✅ 200 | gate |

---

## 3. Discriminators

4 surface routes, `auth: none` (no login needed). All are route-existence flips (200→404).

| # | URL | Notes |
|---|-----|-------|
| 1 | `/support/` | Support index. Master: renders with `require_support_permission` → 200. |
| 2 | `/support/certificates/` | Certificate search tool. |
| 3 | `/support/enrollment/` | Enrollment management. |
| 4 | `/support/contact_us/` | Contact form (slowest surface: 1.8s on master — template render). |

Route block `url(r'^support/', include('support.urls'))` was **always registered** (no feature flag gate) → cleanest discriminator class. Asserted with `auth: none` — no fixture data, no session, no staff user needed.

---

## 4. Gates (No Crash)

| Surface | Verifies |
|---------|----------|
| LMS `/` | No import error from support/zendesk removal |
| `/submit_support_form` | Endpoint renamed from `submit_feedback` → `submit_support`, POST-only → 405 on GET proves route exists |
| Studio `/home/` | CMS starts, no import error |

---

## 5. Vacuous (Excluded by Design)

**`/financial-assistance/*`** — URLs gated on `FEATURES['ENABLE_FINANCIAL_ASSISTANCE_FORM']`. Flag not set in devstack defaults → not registered → 404 on both branches. Not included in checklist.

**Zendesk API routes** — `openedx/core/djangoapps/zendesk_proxy/urls.py` was always imported via `lms/urls.py` at `/api/zendesk_proxy/`. However, the v0/v1 views call Zendesk API which requires `ZENDESK_URL/USER/API_KEY` (all `None` by default) → even on master the views would error. Route-level 404 vs non-404 may work but is fragile — skipped in favor of the cleaner support routes.

---

## 6. Uncovered (Manual Only)

- `lms/djangoapps/certificates/views/support.py` → support certificate views deleted
- `lms/djangoapps/instructor/services.py` → support enrollment service deleted
- `cms/djangoapps/contentstore/views/item.py` / `settings_data_config.py` → support refs stripped
- `lms/djangoapps/branding/api.py` → support footer link removed
- `lms/templates/header/header.html`, `help_modal.html` → support UI links removed
- Zendesk proxy v0/v1 API endpoints at `/api/zendesk_proxy/v0/` and `/api/zendesk_proxy/v1/`
- Webpack entries (`support` JS bundles) removed from `webpack-config/file-lists.js`

---

## 7. Run History

| Run | Branch | Result | Note |
|:---:|--------|:---:|------|
| 1 | support-zendesk-rm | 6/7 | `/submit_support_form` returned 405 not 200 (POST-only) |
| 2 | support-zendesk-rm | 7/7 | Fixed assertion: 405 proves route exists |
| 3 | master | 3/7 | 4 support routes FAIL (200 on master → discriminators confirmed) |

---

## 8. Cross-Reference

| Artifact | Location |
|----------|----------|
| Checklist YAML | `platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/pr-2324.yml` |
| PR worktree | `/Users/noahwang/workspace/hawthorn/platform-support-zendesk-removal` |
| PR #2322 results | `devstack/docs/pr-2322-verification.md` |
| PR #2323 results | `devstack/docs/pr-2323-verification.md` |
