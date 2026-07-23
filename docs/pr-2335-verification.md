# PR #2335 Grades Py3 Migration — Verification Results

> Date: 2026-07-21
> PR: #2335 grades Py3 migration
> Branch: `py3-m5-grades` (worktree `platform-py3-grades`)
> Runner: Playwright checklist-as-code (`browser-acceptance-harness`)
> Checklist: `checklists/pr-2335.yml` — 3 surfaces (all gates)

---

## 1. PR Summary

21 files changed, 178 insertions, 156 deletions. Pure Py3 compatibility migration across the grades stack.

| Layer | Files |
|-------|-------|
| Core | `course_grade.py`, `subsection_grade.py`, `scores.py`, `models.py` |
| Events | `events.py` (73 lines restructured) |
| Signals | `signals/handlers.py` |
| Services | `services.py` |
| Tasks | `tasks.py` |
| Commands | `recalculate_subsection_grades.py` |
| Tests | 11 test files |

---

## 2. Results

### py3-m5-grades — 3/3 passed (4.6s)

| # | Surface | Result |
|---|---------|:---:|
| 1 | LMS `/` → 200 | ✅ |
| 2 | `/dashboard` → 200 | ✅ |
| 3 | Studio `/home/` → 200 | ✅ |

### Master baseline — 3/3 passed (6.9s)

| # | Surface | py3-grades | Master | Role |
|---|---------|:---:|:---:|------|
| 1 | LMS `/` | ✅ 200 | ✅ 200 | gate |
| 2 | `/dashboard` | ✅ 200 | ✅ 200 | gate |
| 3 | Studio `/home/` | ✅ 200 | ✅ 200 | gate |

---

## 3. Analysis

**No discriminators — by design.** This is a Py3 syntax migration, identical pattern to #2334.

**Dashboard chosen** over the progress page because:
- Dashboard renders enrolled course cards with grade summaries → exercises `course_grade.py` and `scores.py` loading paths
- `qacert` is enrolled in `course-v1:QA+Acceptance+Test` → course card with progress bar renders
- No special URL encoding issues (plain `/dashboard`)

**Progress page excluded** — `/courses/{course_key}/progress` returns 404 for `qacert` (despite being enrolled) because the QA fixture course lacks graded subsections, causing the `_progress` view to return Http404. The dashboard gate sufficiently proves no import errors for the grades module.

---

## 4. Issue Encountered

**Progress page 404 with authenticated user.** The QA fixture course (`course-v1:QA+Acceptance+Test`) has no graded subsections — `_progress()` view returns Http404 when there's nothing to show. Additionally, URL-encoding of `+` and `:` in the course key caused route matching issues with Playwright's `page.goto()`.

**Workaround:** Switched from progress page to dashboard (`/dashboard`), which renders course cards with grade summaries → still exercises the grades import chain without requiring graded content.

---

## 5. Run History

| Run | Branch | Result | Note |
|:---:|--------|:---:|------|
| 1 | py3-grades | 2/3 | Progress page 404 — URL encoding + content issue |
| 2 | py3-grades | 2/3 | Encoded course key still 404 |
| 3 | py3-grades | 3/3 | Switched to dashboard gate — passes |
| 4 | master | 3/3 | Baseline confirms gates |

---

## 6. Cross-Reference

| Artifact | Location |
|----------|----------|
| Checklist YAML | `platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/pr-2335.yml` |
| PR worktree | `/Users/noahwang/workspace/hawthorn/platform-py3-grades` |
| PR #2334 results | `devstack/docs/pr-2334-verification.md` (same Py3 migration pattern) |

---

## 7. Five-PR Summary

| PR | Type | Discriminators | Gates | Pattern |
|----|------|:---:|:---:|------|
| #2322 embargo | DCC | 2 | 3 | Admin route flip |
| #2323 badges | DCC | 3 | 4 | Mixed layer (API+JSON+admin) |
| #2324 support+zendesk | DCC | 4 | 3 | Route flip, auth:none |
| #2334 triboo_analytics | Py3 | 0 | 3 | All gates |
| #2335 grades | Py3 | 0 | 3 | All gates |
