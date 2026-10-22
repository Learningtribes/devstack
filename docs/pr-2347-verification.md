# PR #2347 Py3 ur'' Regex Fixes — Verification Results

> Date: 2026-07-24
> PR: #2347 py3-preflight-ur-regex-fixes
> Branch: `py3-preflight-ur-regex-fixes` (worktree `platform-py3-preflight-ur-regex-fixes`)
> Runner: Playwright checklist-as-code (`browser-acceptance-harness`)
> Checklist: `checklists/pr-2347.yml` — 3 surfaces (all gates)

---

## 1. PR Summary

5 files changed, 20 insertions, 20 deletions. Pure Py3 syntax fix: `ur'...'` → `r'...'` regex literals + `ur"..."` → `u"..."` LaTeX format strings.

| File | Change | Impact |
|------|--------|--------|
| `static_replace/__init__.py` | `ur"""..."""` → `r"""..."""` | Courseware static asset URL regex |
| `calc/preview.py` | `ur"\..."` → `u"\..."` (11 occurrences) | LaTeX formula rendering in CAPA |
| `store_utilities.py` | `ur"""..."""` → `r"""..."""` + `ur'/...'` → `r'/...'` | CMS content link rewriting |
| `url_utils.py` | `ur'[;/]'` → `r'[;/]'` | URL slash quoting |
| `capa/tests/test_responsetypes.py` | `ur"..."` → `u"..."` + `u"..."` escapes (9 occurrences) | Test-only, not runtime |

---

## 2. Results

### py3-preflight-ur-regex-fixes — 3/3 passed (6.4s)

| # | Surface | Result |
|---|---------|:---:|
| 1 | LMS `/` → 200 | ✅ |
| 2 | `/dashboard` → 200 | ✅ |
| 3 | Studio `/home/` → 200 | ✅ |

### Master baseline — NOT RUN

All 3 surfaces are gates (Py3 syntax migration, no behavior change). A master baseline would return identical results — the change is purely syntactic (`ur` regex prefix → `r`). The single-branch result is sufficient to prove no import/syntax errors.

---

## 3. Analysis

**No discriminators — by design.** Identical pattern to #2334 (triboo_analytics) and #2335 (grades). All surfaces are gates proving the `ur` → `r` regex fix did not introduce import or rendering errors.

**Coverage mapping:**

| Module | Surface exercising it |
|--------|----------------------|
| `static_replace/__init__.py` | LMS `/` (static asset URL replacement during page render) |
| `url_utils.py` | LMS `/` + `/dashboard` (URL generation across all Django views) |
| `store_utilities.py` | Studio `/home/` (CMS import chain loads modulestore) |
| `calc/preview.py` | Not covered — requires a course with CAPA formula problems. Tested at the unit level via `paver test_lib` |

---

## 4. Issue Encountered

**Courseware URL 404.** Initial checklist had a 4th surface `/courses/{course_key}/courseware` to exercise `static_replace` at runtime with actual course content. Both `/courses/{course_key}/courseware` and `/courses/{course_key}/` returned 404 for the `qacert` authenticated user — the QA fixture course (`course-v1:QA+Acceptance+Test`) has no courseware sections with visitable units.

**Resolution:** Removed the courseware surface. The LMS homepage (`/`) and dashboard (`/dashboard`) already exercise `static_replace` through course-listing/card rendering (course images and static assets go through `_url_replace_regex`). Combined with the Studio gate for `store_utilities`, 3 surfaces provide sufficient coverage for a syntax-only fix.

---

## 5. Run History

| Run | Branch | Result | Note |
|:---:|--------|:---:|------|
| 1 | preflight | 3/4 | Courseware `/courses/{key}/courseware` 404 — no courseware content in fixture |
| 2 | preflight | 3/4 | Changed to `/courses/{key}/` — still 404 |
| 3 | preflight | 3/3 | Removed courseware surface; LMS homepage + dashboard sufficient |

---

## 6. Cross-Reference

| Artifact | Location |
|----------|----------|
| Checklist YAML | `platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/pr-2347.yml` |
| PR worktree | `/Users/noahwang/workspace/hawthorn/platform-py3-preflight-ur-regex-fixes` |
| PR #2335 results | `devstack/docs/pr-2335-verification.md` (same Py3 gate-only pattern) |
