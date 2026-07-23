# Py3 Migration — Full Inventory for Cross-Review

> Date: 2026-07-23
> Purpose: Single-source-of-truth for Opus cross-review of all repos, worktrees, branches, PRs, and docs
> Workspace root: `/Users/noahwang/workspace/hawthorn/`

---

## 1. Repositories

| Repo | Type | Purpose |
|------|------|---------|
| `platform/` | Primary (master) | Open edX Hawthorn monolith, git worktree parent |
| `platform-student-py3/` | Worktree | Phase 4 5E student (#2357) |
| `platform-courseware-py3/` | Worktree | Phase 4 5F courseware (#2359) |
| `platform-instructor-py3/` | Worktree | Phase 4 5D instructor (#2360) |
| `platform-contentstore-py3/` | Worktree | Phase 4 5G contentstore (#2361) |
| `platform-phase5-6d-apis/` | Worktree | Phase 5 6D APIs (5 modules) |
| `platform-phase5-6b-core/` | Worktree | Phase 5 6B openedx/core/djangoapps (53 apps) |
| `platform-phase5-6c-libs/` | Worktree | Phase 5 6C core libs (7 libs) |
| `platform-phase5-6a-xmodule/` | Worktree | Phase 5 6A xmodule (8 sub-modules) |
| `platform-embargo-removal/` | Worktree | DCC embargo removal (#2322) |
| `platform-badges-removal/` | Worktree | DCC badges removal (#2323) |
| `platform-support-zendesk-removal/` | Worktree | DCC support+zendesk removal (#2324) |
| `platform-m4-4a-external-auth-entitlements/` | Worktree | DCC M4.4-A (#2348) |
| `platform-m4-module-removal/` | Worktree | DCC combined M4 branch (superseded by splits) |
| `platform-py3-grades/` | Worktree | Phase 4 5C grades (#2335, other author) |
| `platform-py3-triboo-analytics/` | Worktree | Phase 4 5B triboo_analytics (#2334, other author) |
| `platform-migration_discussion/` | Worktree | Migration planning docs + skill references |
| `platform-browser-acceptance-harness/` | Worktree | Playwright browser testing harness + checklists |
| `devstack/` | Project | Docker Compose devstack (LMS + CMS + MySQL + MongoDB + ES) |
| `edx-ora2/` | Fork | Vendored source (6F, pending) |
| `edx-search/` | Fork | Vendored source (6F, pending) |
| `src/` | Dependencies | Pip-installed XBlocks + vendored packages |

---

## 2. Active Branches & PRs

### Phase 4 — Our PRs (4 open)

> ⚠️ Update 2026-07-23: 全部 8 个 Phase4/5 PR 的 GitHub base 已由 `master` 改为 `embargo-removal-squashed`（已推 origin），
> 以去除 diff 中约 −3,700 行 embargo 删除噪音。下方 Files/± 为**去噪后**的纯 py3 体量。DCC #2322 合入 master 后须回切 master（见 `execution-checklist-20260723.md` 的「选项 A 收尾」）。

| PR | Branch | Worktree | Module | Files | +/− | Base | GH CI |
|:---:|------|------|------|:---:|------|------|------|
| #2357 | `student-py3-analysis` | `platform-student-py3` | student (5E) | 32 | +106/−19 | embargo-squashed | ✅ |
| #2359 | `courseware-py3` | `platform-courseware-py3` | courseware (5F) | 45 | +127/−73 | embargo-squashed | ✅ |
| #2360 | `instructor-py3` | `platform-instructor-py3` | instructor (5D) | 22 | +31/−10 | embargo-squashed | ✅ |
| #2361 | `contentstore-py3` | `platform-contentstore-py3` | contentstore (5G) | 88 | +286/−195 | embargo-squashed | ✅ |

### Phase 5 — Open PRs (4 open, all `[DRAFT!!!]`)

| PR | Branch | Worktree | Batch | Modules | Files | +/− | Base | GH CI |
|:---:|------|------|-------|------|:---:|------|------|------|
| #2362 | `phase5-6d-apis` | `platform-phase5-6d-apis` | 6D | certificates, discussion_api, extended_api, bulk_email, lti_provider | 36 | +49/−10 | embargo-squashed | ✅ |
| #2363 | `phase5-6b-core` | `platform-phase5-6b-core` | 6B | 53 apps under `openedx/core/djangoapps/` | 404 | +672/−211 | embargo-squashed | ✅ |
| #2364 | `phase5-6c-libs` | `platform-phase5-6c-libs` | 6C | capa, calc, chem, symmath, safe_lxml, dogstats, sandbox-packages | 37 | +98/−56 | embargo-squashed | ✅ (T1 修复 except 后转绿) |
| #2365 | `phase5-6a-xmodule` | `platform-phase5-6a-xmodule` | 6A | xmodule (8 sub-modules) | 106 | +517/−274 | embargo-squashed | ✅ (T1 修复 except 后转绿) |

### DCC Removal — Open PRs (4 open)

| PR | Branch | Worktree | Module | Files | +/− | mergeable |
|:---:|------|------|------|:---:|------|------|
| #2322 | `embargo-removal` | `platform-embargo-removal` | embargo | 61 | +26/−3,727 | MERGEABLE (APPROVED) |
| #2323 | `badges-removal` | `platform-badges-removal` | badges | 99 | +45/−5,044 | MERGEABLE (APPROVED) |
| #2324 | `support-zendesk-removal` | `platform-support-zendesk-removal` | support+zendesk | 156 | +219/−8,802 | 已解冲突 (T2)；APPROVED |
| #2348 | `m4-4a-external-auth-entitlements` | `platform-m4-4a-external-auth-entitlements` | external_auth+entitlements | 96 | +836/−8,342 | MERGEABLE |

### Common Base

| Commit | Branch | Description |
|------|------|------|
| `21690c0c708` | `embargo-removal-squashed` | Squashed embargo removal（与 #2322 逐字节一致：72 files +58/−4039）；**已推 origin**，现作为 8 个 Phase4/5 PR 的临时 GitHub base。DCC 合入后删除 |

---

## 3. Branch Dependency Graph

```
master (8db868ed589)
  │
  ├── embargo-removal-squashed (21690c0c708) ← shared base
  │     │
  │     ├── student-py3-analysis (#2357) ─── Phase 4 5E
  │     ├── courseware-py3 (#2359) ─── Phase 4 5F
  │     ├── instructor-py3 (#2360) ─── Phase 4 5D
  │     ├── contentstore-py3 (#2361) ─── Phase 4 5G
  │     ├── phase5-6d-apis ─── Phase 5 6D
  │     ├── phase5-6b-core ─── Phase 5 6B
  │     ├── phase5-6c-libs ─── Phase 5 6C
  │     └── phase5-6a-xmodule ─── Phase 5 6A
  │
  ├── embargo-removal (#2322) ─── DCC (MERGEABLE)
  ├── badges-removal (#2323) ─── DCC (MERGEABLE)
  ├── support-zendesk-removal (#2324) ─── DCC (MERGEABLE)
  └── m4-4a-external-auth-entitlements (#2348) ─── DCC M4.4-A (MERGEABLE)
```

**Rebase plan**: embargo (#2322) merges first → 8 branches rebase onto master. Then badges (#2323) → certificates/extended_api references fixed. Then support+zendesk (#2324) → courseware/instructor references fixed.

---

## 4. Cross-App Import Dependencies

Modules our PRs import from DCC-pending modules:

| PR | Module | badges | support+zendesk | entitlements |
|:---:|------|:---:|:---:|:---:|
| #2357 | student | — | — | `CourseEntitlement` (2 refs) |
| #2359 | courseware | — | `_record_feedback_in_zendesk` (1 ref) | — |
| #2360 | instructor | — | `create_zendesk_ticket` (1 ref) | — |
| #2361 | contentstore | — | — | — |
| 6D | certificates | `badges.events/utils` (6 refs) | — | — |
| 6D | extended_api | `badges.utils.site_prefix` (1 ref) | — | — |
| 6D | discussion_api | — | — | — |
| 6D | bulk_email | — | — | — |
| 6D | lti_provider | — | — | — |
| 6B | (53 apps) | — | — | — |
| 6C | (7 libs) | — | — | — |
| 6A | xmodule | — | — | — |

All imports are pre-existing — our changes don't add or remove any. DCC PRs will remove them when merged.

---

## 5. Changes Summary

| Category | Files | +/− | Syntax Errors Fixed |
|------|:---:|------|:---:|
| Phase 4 (4 PRs) | 188 | +545/−294 | 2 (`except E,e:`, `print`) |
| Phase 5 (4 branches) | 585 | +1338/−548 | 15 (`raise`, `print`, `except`, `ur''`, lambda) |
| **Total** | **773** | **+1883/−842** | **17** | ← 各分类 diff 算术和。**累积 vs merge-base `ae5411201c3` = 829 files / +1912 / −4575**（实测，口径见 `integration-branch-analysis.md` §0）|

### Change Types Breakdown

| Pattern | Phase 4 | Phase 5 | Total |
|------|:---:|:---:|:---:|
| `__future__` imports | ~120 | ~600 | ~720 |
| `unicode()` → `text_type()` | ~230 | ~270 | ~500 |
| `.iteritems()` → `six.iteritems()` | ~15 | ~125 | ~140 |
| `basestring` → `six.string_types` | ~10 | ~80 | ~90 |
| `xrange()` → `range()` | ~3 | ~7 | ~10 |
| `except E, e:` → `except E as e:` | 2 | 15 | 17 |
| `print` → `print()` | 1 | 12 | 13 |
| `raise E, V, T` → `six.reraise()` | 0 | 5 | 5 |
| `ur'...'` → `r'...'` | 0 | 1 | 1 |
| lambda tuple unpack → `kv[1]` | 0 | 1 | 1 |

---

## 6. Known Issues & Reusable Patterns

### Pitfalls (documented in `devstack/docs/`)

| Doc | Content |
|-----|---------|
| `future-import-pitfalls.md` | `unicode_literals` 🔴 / `absolute_import` ⚠️ / `division`+`print_function` ✅ |
| `pyc-stale-cache-removal.md` | Stale `.pyc` in removed module dirs → `RuntimeError` |
| `py3-migration-environment.md` | Py3.8 container strategy (compileall-only, no full Django) |

### Recurring Bugs

| Bug | Occurrences | Pattern |
|-----|:---:|------|
| `absolute_import` breaks implicit relative imports | 3 (student, 6B, 6B) | `from .module import` |
| `self._x.iteritems()` regex bug → `self.six.iteritems()` | 2 (6B, 6A) | Manual: `six.iteritems(self._x)` |
| `print` multi-line with `\` continuation | 2 (6B, 6A) | Manual merge |
| `import six` vs `from six import iteritems` | 2 (contentstore) | `six.iteritems()` needs `import six` |
| Missing `text_type` import | 2 (instructor, 6B) | Script pattern-match fail |
| Missed `except E, e:` in subdirectories | 1 (6C) | CI caught 15 missed |

---

## 7. Test Results

| Branch | Suite | Pass | Fail |
|------|------|:---:|:---:|
| student-py3-analysis | LMS student | 569 | 0 |
| student-py3-analysis | CMS contentstore | 1165 | 0 |
| courseware-py3 | LMS courseware | 1129 | 0 |
| courseware-py3 | CMS contentstore | All | 0 |
| instructor-py3 | LMS instructor | All | 0 |
| instructor-py3 | CMS contentstore | All | 0 |
| contentstore-py3 | CMS contentstore | All | 0 |
| phase5-6d-apis | LMS certificates+discussion+extended+bulk+lti | All | 0 |
| phase5-6b-core | LMS user_api+bookmarks+course_groups+ace+programs+site_config+content | 1030 | 0 |
| phase5-6b-core | CMS contentstore | All | 0 |
| phase5-6c-libs | GH Py3 Syntax Check | ✅ green | 0 (T1 修复 `except E,e:` 遗漏后) |
| phase5-6a-xmodule | GH Py3 Syntax Check | ✅ green | 0 (T1 修复 `except E,e:` 遗漏后) |

> Jenkins `pr-head`：全 Phase4/5 PR 曾显示 aborted，改 base 后重新排队构建中（pending，非真失败）。待 T4 定性。

---

## 8. Docs Index

| Path | Content |
|------|---------|
| `devstack/docs/phase4-progress.md` | Phase 4 detail + worktree map |
| `devstack/docs/phase5-coverage-gap.md` | Phase 5 detail + remaining 6E/6F |
| `devstack/docs/pr-2357-verification.md` | Student verification report |
| `devstack/docs/pr-2357-review-comment.md` | Student PR review comment |
| `devstack/docs/pr-2359-verification.md` | Courseware verification report |
| `devstack/docs/pr-2359-review-comment.md` | Courseware PR review comment |
| `devstack/docs/pr-2360-verification.md` | Instructor verification report |
| `devstack/docs/pr-2360-review-comment.md` | Instructor PR review comment |
| `devstack/docs/pr-2361-verification.md` | Contentstore verification report |
| `devstack/docs/pr-2361-review-comment.md` | Contentstore PR review comment |
| `devstack/docs/future-import-pitfalls.md` | `__future__` risk grading |
| `devstack/docs/pyc-stale-cache-removal.md` | `.pyc` cleanup guide |
| `devstack/docs/py3-migration-environment.md` | Py3.8 test environment |
| `platform-migration_discussion/docs/migration_discussion/` | Planning docs (01–11) |
| `platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/` | Browser checklists (pr-2357 through pr-2361) |

---

## 9. Remaining Work

| Area | Scope | Blocker |
|------|------|------|
| 4 Phase 4 PRs rebase | Rebase onto master after DCC merges | DCC PRs |
| M4.4-B (teams SPLIT) | Cut from combined M4 branch | DCC #2322–#2324 merged |
| Phase 4 blocked modules | teams, PE, dcc, verify_student | M4.4-B |
| Phase 5 6E utilities | ~15K SLOC production + 42K test infra | Low priority |
| Phase 5 6F vendored src/ | ~70K SLOC, ora2+proctoring | Upstream fork decision |
| Py3.8 Django runtime | Full `paver test_system` under Py3 | Celery 4.4 bridge |
