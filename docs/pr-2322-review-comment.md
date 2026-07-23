## Browser Acceptance Testing — ✅ Verified

Ran 5-surface Playwright checklist against a live devstack with the `embargo-removal` worktree mounted. Double-run baseline on `master` confirms 2 discriminators.

### Results

| # | Surface | Master | embargo-rm | Role |
|---|---------|:---:|:---:|------|
| 1 | `/triboo-guanli/embargo/restrictedcourse/` | ❌ 200 | ✅ 404 | **discriminator** |
| 2 | `/triboo-guanli/embargo/ipfilter/` | ❌ 200 | ✅ 404 | **discriminator** |
| 3 | LMS `/` | ✅ 200 | ✅ 200 | gate (no import error) |
| 4 | `/course_modes/choose/{course}/` | ✅ 200 | ✅ 200 | gate (embargo check stripped) |
| 5 | Studio `/home/` | ✅ 200 | ✅ 200 | gate (no import error) |

**5/5 green on embargo-removal. 2 discriminators proven (route-existence flip: 200 → 404).**

### Discriminators

Both are admin-route assertions at `/triboo-guanli/` (fork custom mount, not `/admin/`). On `master`, `RestrictedCourse` and `IPFilter` are registered in `embargo/admin.py` → admin page renders (200). On `embargo-removal`, models are deleted → 404. Route-level, no fixture data needed — strongest discriminator class.

### Why not `/embargo/` or `/api/embargo/`?

Those routes are gated on `FEATURES['EMBARGO']` which defaults `False` on master → not registered → 404 on both branches. Enabling it just to flip to non-404 would be self-inflicted. Admin routes are always active under `DEBUG=True` in devstack, making them the reliable discriminator layer.

### Vacuous (caught & removed)

`/triboo-guanli/embargo/countryaccessrule/` — `CountryAccessRule` is a `StackedInline`, never registered standalone via `admin.site.register()`. Returns 404 on BOTH branches. Deleted from checklist after baseline proof.

### Uncovered (manual only)

- `change_enrollment` POST — `embargo_api.redirect_if_blocked()` call-site stripped in `student/views/management.py`
- `verify_student/views.py` — same pattern
- Course rerun in `contentstore/tasks.py` — `RestrictedCourse`/`CountryAccessRule` copy logic deleted
- `edx-enterprise` compatibility — the API stub (`redirect_if_blocked` → `None`) is consumed externally

### Checklist

```yaml
# platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/pr-2322.yml
pr: 2322
surfaces: 5 (2 discriminators + 3 gates)
```

Full verification log: `devstack/docs/pr-2322-verification.md`
