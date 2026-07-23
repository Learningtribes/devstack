# Py3 Migration — Coverage Gap & Phase 5 Analysis

> Date: 2026-07-23 (updated with completed batches)
> Source: `platform-migration_discussion/docs/migration_discussion/11-phase5-module-inventory-20260715.md`

---

## 1. Headline

| Stage | Modules | SLOC | py3-err | Status |
|-------|:---:|-----|:---:|:---:|
| Phase 0–3 (merged) | ~22 | 19K | 0 | ✅ |
| Phase 4 (our PRs) | 4 | ~84K | — | 🟡 4 PRs open |
| Phase 4 (blocked) | 4 | ~15K | — | 🔴 M4.4-B |
| Phase 4 (others) | 3 | ~27K | — | 1 merged, 2 open |
| DCC removal (open) | 4 | −14K | — | 🟡 4 PRs open |
| Phase 5 6D | 5 | ~27K | 0 | ✅ `phase5-6d-apis` |
| Phase 5 6B | 53 | ~61K | 7 | ✅ `phase5-6b-core` |
| Phase 5 6C | 7 | ~19K | 7 | ✅ `phase5-6c-libs` |
| Phase 5 6A | 8 | ~94K | 27 | ✅ `phase5-6a-xmodule` |
| **Phase 5 subtotal** | **73** | **~201K** | **41** | **4 branches pushed** |
| Phase 5 6E | ~17 | ~57K | 5 | ⬜ 散碎+测试基础设施 |
| Phase 5 6F | 24 | ~70K | 27 | ⬜ vendored，需上游决策 |
| **Total remaining** | **~41** | **~127K** | **32** | |

---

## 2. Phase 5 Completed Branches

| Branch | Batch | Modules | Files | +/− | Issues |
|------|-------|------|:---:|------|:---:|
| `phase5-6d-apis` | 6D | certificates, discussion_api, extended_api, bulk_email, lti_provider | 36 | +49/−10 | 0 |
| `phase5-6b-core` | 6B | 53 apps (openedx/core/djangoapps) | 407 | +677/−211 | 4 (absolute_import, self.six, unicode_literals, print) |
| `phase5-6c-libs` | 6C | capa, calc, chem, symmath, safe_lxml, dogstats, sandbox-packages | 36 | +96/−54 | 1 (missed except E,e:) |
| `phase5-6a-xmodule` | 6A | xmodule (8 sub-modules) | 106 | +516/−273 | 4 (reraise, print multi-line, complex iteritems, bracket notation) |
| **Total** | | **73 modules** | **585** | **+1338/−548** | **9 issues** |

---

## 3. Issues Summary (Phase 5)

| # | Type | Affected | Fix |
|---|------|----------|-----|
| 1 | `absolute_import` broke `import accounts` etc | user_api, cors_csrf | `from . import` |
| 2 | `self._x.iteritems()` → `self.six.iteritems()` (regex bug) | block_structure, capa | Manual: `six.iteritems(self._x)` |
| 3 | `unicode_literals` test dependency | email_opt_in_list | Restored, kept xrange fix |
| 4 | `print` multi-line with `\` continuation | verified_track_content | Manual merge |
| 5 | `raise E, V, T` → `six.reraise()` | xmodule (5 files) | Manual |
| 6 | Bracket-notation `.iteritems()` (`dict['key'].iteritems()`) | xmodule, split_mongo | Manual |
| 7 | Method-chain `.iteritems()` (`fn().iteritems()`) | split_migrator | Manual |
| 8 | Dict-literal `.iteritems()` | mongo/base | Manual |
| 9 | Missed `except E, e:` (15 occurrences) | capa, symmath, sandbox | `except E as e:` |

---

## 4. Remaining — 6E + 6F

### 6E — utilities (~57K SLOC, skip)

Bulk (42K/174 files) is `common/test/acceptance` — test infrastructure, not production code. Remaining ~15K SLOC scattered across `lms/lib`, `cms/lib`, `course_experience`, `learner_profile`, `microsite_configuration`, etc. Low priority — small modules with minimal Py2 patterns.

### 6F — vendored src/ (~70K SLOC, blocked on decisions)

| package | SLOC | Errors | Blocker |
|------|-----|:---:|------|
| edx-ora2 | 24,802 | 8 | 🔴 Hard dependency, no upstream Py3 fork |
| edx-proctoring | 10,889 | 1 | 🔴 Hard dependency, no upstream Py3 fork |
| django-wiki | 4,993 | 4 | Forked version |
| pystache-custom | 4,075 | 5 | Duplicate with -dev |
| xblock-drag-and-drop-v2 | 4,845 | 0 | Clean |
| edx-search | 4,210 | 0 | Clean |
| Others (18 packages) | ~16K | 9 | Various |

---

## 5. DCC PRs (Blocking Rebase)

All 4 Phase 4 PRs + 4 Phase 5 branches share `embargo-removal-squashed` base. Rebase onto master requires:

| PR | Module | Status |
|:---:|------|:---:|
| #2322 | embargo | 🟡 MERGEABLE, Jenkins ✅ |
| #2323 | badges | 🟡 MERGEABLE, Jenkins ✅ |
| #2324 | support+zendesk | 🟡 MERGEABLE, Jenkins ✅ |
| #2348 | external_auth+entitlements | 🟡 M4.4-A |

---

## 6. Docs Index

| Document | Content |
|----------|---------|
| `phase4-progress.md` | Phase 4 completed + blocked + worktree map |
| `phase5-coverage-gap.md` | This document |
| `pr-2357-verification.md` | Student verification |
| `pr-2359-verification.md` | Courseware verification |
| `pr-2360-verification.md` | Instructor verification |
| `pr-2361-verification.md` | Contentstore verification |
| `future-import-pitfalls.md` | `__future__` risk grading |
| `pyc-stale-cache-removal.md` | `.pyc` cleanup guide |
| `py3-migration-environment.md` | Py3.8 test container strategy |
