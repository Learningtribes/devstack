## `paver test_system` — ✅ LMS + CMS Both Green

### Results

| Suite | Pass | Fail |
|-------|:---:|:---:|
| LMS `lms/djangoapps/instructor` | All | 0 |
| CMS `cms/djangoapps/contentstore` | All | 0 |

One fix needed: `text_type` import placement in `instructor_task_helpers.py` (django import path differed from script assumption; 5 tests caught it).

### Nature of This PR

Py3 compatibility migration (23 files, +31/−10) — smallest and cleanest of the three Phase 4 modules. Key changes:
- `except DashboardError, error:` → `except DashboardError as error:` (tools.py)
- `unicode()` → `text_type()` (6 calls across 3 files)
- `.has_key()` → `'in'` operator (api.py)
- `__future__` imports (20 added, 2 fixed)

### Phase 4 Progress

| # | Module | Batch | LOC | Status |
|:---:|------|:---:|:---:|:---:|
| 2357 | student | 5E | ~24K | ✅ |
| 2359 | courseware | 5F | ~34K | ✅ |
| 2360 | instructor | 5D | ~5.5K | ✅ |

### Checklist

```yaml
# platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/pr-2360.yml
pr: 2360
surfaces: 3 (all gates — Py3 migration, no removals)
```

Full verification log: `devstack/docs/pr-2360-verification.md`
