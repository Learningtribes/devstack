# PR #2357 Student Py3 Migration — Verification Results

> Date: 2026-07-22
> PR: #2357 [DRAFT] Student Py3 migration
> Branch: `student-py3-analysis` (worktree `platform-student-py3`)
> Commit: `42fd2afb8f7` (5 commits ahead of master)
> Checklist: `checklists/pr-2357.yml` — 4 surfaces (all gates)

---

## 1. PR Summary

32 files changed, 101 insertions, 14 deletions. Pure Py3 compatibility migration — no module removal. All changes use standard `six` compatibility patterns.

| Type | Files | Impact |
|------|-------|--------|
| `__future__` imports | 31 files | `absolute_import, division, print_function` (no `unicode_literals`) |
| `unicode()` → `text_type()` | dashboard.py (×8), management.py (×1) | ILT session URLs, enrollment redirect |
| `basestring` → `six.string_types` | management.py (×1) | `admin_panel_account_creation` |
| `urlparse` → `six.moves.urllib.parse` | login.py, helpers.py | Login flow, URL helpers |
| `except IOError, ex:` → `except IOError as ex:` | session_invitation_pdf.py (×1) | PDF image loading |

---

## 2. Issues Found and Fixed

### Issue 1: `absolute_import` broke implicit relative imports

**Symptom**: `ImportError: No module named admin_panel` during Django startup (`email_marketing/signals.py` → `student.views` → `from admin_panel import *`).

**Root cause**: Adding `from __future__ import absolute_import` to `views/__init__.py` changed 5 implicit relative imports to absolute imports. `admin_panel`, `dashboard`, `login`, `management`, `session_invitation_pdf` are sibling modules in the `views/` package — they need explicit `.` prefix.

**Fix**: Changed 5 imports in `views/__init__.py`:
```diff
-from admin_panel import *
+from .admin_panel import *
 (same for dashboard, login, management, session_invitation_pdf)
```
Commit: `42fd2afb8f7`

### Issue 2: `unicode_literals` changed string literal types

**Symptom**: 11 test failures in `test_reset_password.py` (2), `test_email.py` (5), mock assertions (4). All were `repr()` mismatch — expected `"('template.html', [])"` but got `u"(u'template.html', [])"`.

**Root cause**: `unicode_literals` makes all string literals `unicode` in Py2.7, causing tuple/list `repr()` to include `u''` prefixes. The actual behavior is identical — only string representations changed.

**Fix**: Removed `unicode_literals` from all 31 `__future__` imports. Kept `absolute_import, division, print_function`. Commit: `42fd2afb8f7`

### Issue 3: Stale `.pyc` files in removed embargo module

**Symptom**: `RuntimeError: EmbargoedCourse doesn't declare an explicit app_label and isn't in an application in INSTALLED_APPS` when running CMS test suite.

**Root cause**: Embargo module was removed from `INSTALLED_APPS` (commit `21690c0c708`), but compiled `.pyc` files remained in `openedx/core/djangoapps/embargo/`. Python imported `models.pyc`, Django tried to register the model class → `RuntimeError`.

**Fix**: Deleted stale `.pyc` files and `__pycache__/` from embargo directory. This is a **module-removal pitfall** — always clean `.pyc` after deleting `.py` sources (see `devstack/docs/pyc-stale-cache-removal.md`).

---

## 3. Test Results

### Static Verification

| Check | Result |
|-------|:---:|
| Python 3.8 `compileall` (Docker py38-tool-container) | ✅ PASS |
| Python 2.7 `compileall` | ✅ PASS |
| CI `python27-syntax-check.yml` | ✅ |
| CI `compatibility-check.yml` | ✅ |
| CI `test-isolation-check.yml` | ✅ |

### Runtime Verification — `paver test_system`

| Suite | Pass | Fail | Skip | Time |
|-------|:---:|:---:|:---:|------|
| **LMS** `common/djangoapps/student` | 569 | 0 | 17 | 61s |
| **CMS** `cms/djangoapps/contentstore` | 1165 | 0 | 5 | 237s |

### Commit Chain

```
42fd2afb8f7 fix: remove unicode_literals and fix implicit relative imports
5cd41c72288 Modernize Py2-only patterns (step 3)
ed525bfb1fb Add __future__ imports (step 2)
177d46203f4 Fix Py3 syntax error (step 1)
21690c0c708 Remove embargo module (M4.3)
```

---

## 4. Business-PR Intersection Check

4 open business PRs touch `common/djangoapps/student/`:

| PR | Files | Overlap |
|----|-------|---------|
| TRIB-2013 | urls.py, admin_panel.py | urls.py: `__future__` header only → no semantic conflict |
| trib-2020 | feed_update_users commands | No overlap (management commands, not touched) |
| TRIB-1938 | urls.py, admin_panel.py | urls.py: `__future__` header only → no semantic conflict |
| TRIB-1621 | urls.py, admin_panel.py | urls.py: `__future__` header only → no semantic conflict |

---

## 5. filter/map Iterator Semantics Check

| Pattern | Location | Verdict |
|---------|----------|:---:|
| `filter()` (built-in) | `roles.py:140` | Safe — immediately consumed by `for` loop |
| `map()` (built-in) | `csv_registration.py:165` | Safe — consumed by `join()` |
| Django ORM `.filter()` | 139 occurrences | Not affected — QuerySet method, not built-in |
| `iteritems` | All via `six.iteritems` | Already wrapped |

---

## 6. Risk Assessment

| Risk | Level | Rationale |
|------|:---:|------|
| Import error | None | compileall Py2+Py3.8 both pass; runtime tests green |
| Behavioral regression in Py2.7 | None | All changes are Py2-identical; runtime tests green |
| Behavioral regression in Py3.8 | Low | Standard `six` patterns, no custom compat code |
| Business PR conflicts | Low | Only `__future__` header in shared urls.py |
| Runtime test coverage gap | Medium | No Py3.8 Django environment for full runtime test |

---

## 7. Cross-Reference

| Artifact | Location |
|----------|----------|
| Checklist YAML | `platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/pr-2357.yml` |
| PR worktree | `/Users/noahwang/workspace/hawthorn/platform-student-py3` |
| PR review comment | `devstack/docs/pr-2357-review-comment.md` |
| `.pyc` cleanup guide | `devstack/docs/pyc-stale-cache-removal.md` |
| PR #2334 results | `devstack/docs/pr-2334-verification.md` (same Py3 migration pattern) |
| PR #2335 results | `devstack/docs/pr-2335-verification.md` (same Py3 migration pattern) |
