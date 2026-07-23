# Phase 4 Py3 Migration — Progress Report

> Date: 2026-07-23 (updated)
> Base: `embargo-removal-squashed` (`21690c0c708`)
> Strategy: One worktree per module, from common base, `paver test_system` verified

---

## Phase 4 — All Unblocked Modules Complete (4 PRs)

| # | Module | Batch | LOC | Files | CMS | LMS | Issues |
|:---:|------|:---:|-----|:---:|:---:|:---:|:---:|
| 2357 | student | 5E | ~24K | 32 | ✅ | ✅ | 3 (absolute_import, unicode_literals, .pyc) |
| 2359 | courseware | 5F | ~34K | 45 | ✅ | ✅ | 0 |
| 2360 | instructor | 5D | ~5.5K | 23 | ✅ | ✅ | 1 (text_type import) |
| 2361 | contentstore | 5G | ~21K | 88 | ✅ | N/A | 2 (six import) |

## Phase 4 — Blocked (4 modules)

| Module | Batch | LOC | Blocker |
|------|:---:|-----|------|
| teams | 5A | ~1.5K | M4.4-B |
| program_enrollments | 5A | ~5.3K | M4.4-B |
| django_comment_client | 5B | ~5K | M4.4-B |
| verify_student | — | — | Delete decision |

## Phase 4 — Others

| # | Module | Batch | Status |
|:---:|------|:---:|:---:|
| 2333 | third_party_auth | 5A | ✅ Merged |
| 2334 | triboo_analytics | 5B | 🟡 Open |
| 2335 | grades | 5C | 🟡 Open |

---

## Issues Encountered & Reusable Docs

| # | Module | Symptom | Root Cause | Fix | Doc |
|---|--------|---------|-----------|-----|-----|
| 1 | student | `ImportError: No module named admin_panel` | `absolute_import` broke implicit relative imports | Added `.` prefix | `future-import-pitfalls.md` |
| 2 | student | 11 test failures (repr mismatch) | `unicode_literals` changed string types | Removed `unicode_literals` | `future-import-pitfalls.md` |
| 3 | student | `RuntimeError: EmbargoedCourse not in INSTALLED_APPS` | Stale `.pyc` in removed embargo | Deleted `.pyc` + `__pycache__/` | `pyc-stale-cache-removal.md` |
| 4 | instructor | `NameError: text_type not defined` | Import insertion matched wrong line | Manual fix | — |
| 5 | contentstore | `NameError: six not defined` | `six.iteritems()` needs `import six` | Changed to `import six` | — |

---

## Worktree Map

```
platform                                     [master]
platform-student-py3                         [student-py3-analysis]    #2357
platform-courseware-py3                      [courseware-py3]          #2359
platform-instructor-py3                      [instructor-py3]          #2360
platform-contentstore-py3                    [contentstore-py3]        #2361
platform-phase5-6d-apis                      [phase5-6d-apis]
platform-phase5-6b-core                      [phase5-6b-core]
platform-phase5-6c-libs                      [phase5-6c-libs]
platform-phase5-6a-xmodule                   [phase5-6a-xmodule]
platform-embargo-removal                     [embargo-removal]
platform-badges-removal                      [badges-removal]
platform-support-zendesk-removal             (detached)
platform-m4-4a-external-auth-entitlements    [m4-4a-external-auth-entitlements]
platform-m4-module-removal                   [m4-module-removal]
platform-py3-grades                          (detached)
platform-py3-triboo-analytics                (detached)
platform-migration_discussion                [migration_discussion]
platform-browser-acceptance-harness          [browser-acceptance-harness]
```
