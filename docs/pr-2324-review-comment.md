## Browser Acceptance Testing — ✅ Verified

Ran 7-surface Playwright checklist against a live devstack with the `support-zendesk-removal` worktree mounted. Double-run baseline on `master` confirms 4 discriminators.

### Results

| # | Surface | Master | support-zendesk-rm | Role |
|---|---------|:---:|:---:|------|
| 1 | `/support/` | ❌ 200 | ✅ 404 | **discriminator** |
| 2 | `/support/certificates/` | ❌ 200 | ✅ 404 | **discriminator** |
| 3 | `/support/enrollment/` | ❌ 200 | ✅ 404 | **discriminator** |
| 4 | `/support/contact_us/` | ❌ 200 | ✅ 404 | **discriminator** |
| 5 | LMS `/` | ✅ 200 | ✅ 200 | gate |
| 6 | `/submit_support_form` | ✅ 405 | ✅ 405 | gate |
| 7 | Studio `/home/` | ✅ 200 | ✅ 200 | gate |

**7/7 green on support-zendesk-removal. 4 discriminators proven (route-existence flip: 200 → 404).**

### Discriminators

All four surfaces use `auth: none` — no login, no fixture data, no staff user needed. Support URLs were registered via a bare `urlpatterns +=` block in `lms/urls.py` with **no feature flag gate**:

```python
urlpatterns += [
    url(r'^support/', include('support.urls')),
]
```

This means the routes are always active on `master`, always 404 on the removal branch. The cleanest discriminator class available — route-existence flip, zero prerequisites.

### Gates

- **LMS `/`** and **Studio `/home/`** — no import errors from removing `support` and `zendesk_proxy` from `INSTALLED_APPS`
- **`/submit_support_form`** — endpoint was renamed from `submit_feedback` to `submit_support` (email-based instead of Zendesk). POST-only → GET returns 405, proving the route still exists.

### Excluded (vacuous by design)

`/financial-assistance/*` — URLs were gated on `FEATURES['ENABLE_FINANCIAL_ASSISTANCE_FORM']` which defaults off. Not registered on master either → skipped.

### Uncovered (manual review recommended)

- `lms/djangoapps/certificates/views/support.py` — deleted, consumed by instructor dashboard cert search
- `lms/djangoapps/instructor/services.py` — `SupportEnrollmentService` deleted
- `cms/djangoapps/contentstore/views/item.py` / `settings_data_config.py` — support references stripped
- `lms/templates/header/header.html`, `help_modal.html` — support UI links removed
- Zendesk proxy API: `/api/zendesk_proxy/v0/` and `/api/zendesk_proxy/v1/` — route-level check skipped (v0/v1 views depend on `ZENDESK_URL/USER/API_KEY` which are `None` by default, making even master responses unreliable)

### Checklist

```yaml
# platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/pr-2324.yml
pr: 2324
surfaces: 7 (4 discriminators + 3 gates)
```

Full verification log: `devstack/docs/pr-2324-verification.md`
