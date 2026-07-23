## `paver test_system` — ✅ LMS + CMS Both Green

### Results

| Suite | Pass | Fail | Skip |
|-------|:---:|:---:|:---:|
| LMS `common/djangoapps/student` | 569 | 0 | 17 |
| CMS `cms/djangoapps/contentstore` | 1165 | 0 | 5 |

### Issues Found and Fixed (3)

| # | Issue | Root Cause | Fix |
|---|-------|-----------|-----|
| 1 | `ImportError: No module named admin_panel` | `absolute_import` made implicit relative imports absolute | Added `.` prefix to 5 imports in `views/__init__.py` |
| 2 | 11 test failures (repr mismatch) | `unicode_literals` changed string literal types → `u"..."` repr | Removed `unicode_literals` from 31 files, kept `absolute_import, division, print_function` |
| 3 | `RuntimeError: EmbargoedCourse not in INSTALLED_APPS` | Stale `.pyc` files in removed embargo module | Deleted `openedx/core/djangoapps/embargo/*.pyc` + `__pycache__/` |

### Nature of This PR

Py3 compatibility migration (32 files, +101/−14) — no module removal. Key changes: `unicode()` → `text_type()`, `basestring` → `six.string_types`, `urlparse` → `six.moves.urllib.parse`, `except E, e:` → `except E as e:`, `__future__` imports (without `unicode_literals`).

### Commit Chain

```
42fd2afb8f7 fix: remove unicode_literals and fix implicit relative imports
5cd41c72288 Modernize Py2-only patterns (step 3)
ed525bfb1fb Add __future__ imports (step 2)
177d46203f4 Fix Py3 syntax error (step 1)
21690c0c708 Remove embargo module (M4.3 base)
```

### Checklist

```yaml
# platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/pr-2357.yml
pr: 2357
surfaces: 4 (all gates — Py3 migration, no removals)
```

Full verification log: `devstack/docs/pr-2357-verification.md`
