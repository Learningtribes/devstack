# PR #2335 Grades Py3 Migration — Verification Results

> Date: 2026-07-21 (3-surface gates); **updated 2026-09-03** (grades v0 API gate)
> PR: #2335 grades Py3 migration
> Branch: `py3-m5-grades` (worktree `platform-py3-m5-grades`)
> Head (2026-09-03): `de00369e7e213a4109e8b4cdf61447b57b6e4457`
> Runner: Playwright checklist-as-code (`browser-acceptance-harness`)
> Checklist: `checklists/pr-2335.yml` — **4 surfaces** (all gates)

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

### 2026-09-03 — py3-m5-grades — 4/4 passed (7.0s)

Local devstack, `PLATFORM_MOUNT=platform-py3-m5-grades`, HEAD `de00369e7e2`.

| # | Surface | Result | Role |
|---|---------|:---:|------|
| 1 | LMS `/` → 200 | ✅ | gate |
| 2 | `/dashboard` → 200 | ✅ | gate |
| 3 | Studio `/home/` → 200 | ✅ | gate |
| 4 | `GET /api/grades/v0/course_grade/{course_key}/users/?username={username}` (`request: true`) → 200 | ✅ | gate |

Surface 4 body (103ms):

```json
[{"username":"qacert","letter_grade":null,"percent":0.0,"course_key":"course-v1:QA+Acceptance+Test","passed":false}]
```

This hits `UserGradeView` → `CourseGradeFactory().read()` and asserts the serialized `course_key` in the raw JSON. Dashboard HTML does not. v0 (session, learner self-read) not v1 (JWT `grades:read`).

Master was not re-run for surface 4: this is a Py3-compat **gate** (expected 200 on both trees), not a discriminator. The 2026-07-21 master double-run still covers surfaces 1–3.

### 2026-07-21 — 3/3 passed (historical)

| # | Surface | py3-grades | Master | Role |
|---|---------|:---:|:---:|------|
| 1 | LMS `/` | ✅ 200 | ✅ 200 | gate |
| 2 | `/dashboard` | ✅ 200 | ✅ 200 | gate |
| 3 | Studio `/home/` | ✅ 200 | ✅ 200 | gate |

---

## 3. Analysis

**No discriminators — by design.** This is a Py3 syntax migration, identical pattern to #2334.

**Dashboard** (surfaces 1–3) only proves the LMS/CMS process imports without 500.

**Grades v0 API** (surface 4) is the grades-stack gate: `request: true` so assertions hit the raw JSON (`page.goto` drops `Accept` and would fetch HTML). Session cookie from `/auto_auth` is enough — `UserGradeView` allows a learner to read her own grade.

**Progress page still excluded** — `/courses/{course_key}/progress` returns 404 for `qacert` because the QA fixture course has no graded subsections (`_progress` Http404). The API gate does not need graded subsections.

---

## 4. Issue Encountered

**Progress page 404 with authenticated user (2026-07-21).** The QA fixture course (`course-v1:QA+Acceptance+Test`) has no graded subsections — `_progress()` returns Http404. URL-encoding of `+` and `:` in the course key also broke `page.goto()`.

**Workaround then:** dashboard HTML gate.

**2026-09-03:** keep dashboard; add the v0 JSON API. Path and `%2B`-encoded course keys both returned 200 with the same `course_key` string.

**Local port 18000 (2026-09-03):** `financial-data-ingestion-hub-local-pg-api-1` was bound to `127.0.0.1:18000`. Stopped for the run, LMS/Studio stopped afterward, that container restarted.

---

## 5. Run History

| Run | Date | Branch | Result | Note |
|:---:|------|--------|:---:|------|
| 1 | 2026-07-21 | py3-grades | 2/3 | Progress page 404 — URL encoding + content issue |
| 2 | 2026-07-21 | py3-grades | 2/3 | Encoded course key still 404 |
| 3 | 2026-07-21 | py3-grades | 3/3 | Switched to dashboard gate — passes |
| 4 | 2026-07-21 | master | 3/3 | Baseline confirms gates 1–3 |
| 5 | 2026-09-03 | py3-m5-grades `de00369e7e2` | **4/4** | Added grades v0 API `request:true` JSON gate |

---

## 6. Cross-Reference

| Artifact | Location |
|----------|----------|
| Checklist YAML | `platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/pr-2335.yml` |
| PR worktree | `/Users/noahwang/workspace/hawthorn/platform-py3-m5-grades` |
| PR #2334 results | `devstack/docs/pr-2334-verification.md` (same Py3 migration pattern) |

---

## 7. Five-PR Summary

| PR | Type | Discriminators | Gates | Pattern |
|----|------|:---:|:---:|------|
| #2322 embargo | DCC | 2 | 3 | Admin route flip |
| #2323 badges | DCC | 3 | 4 | Mixed layer (API+JSON+admin) |
| #2324 support+zendesk | DCC | 4 | 3 | Route flip, auth:none |
| #2334 triboo_analytics | Py3 | 0 | 3 | All gates |
| #2335 grades | Py3 | 0 | **4** | HTML gates + grades v0 JSON API |
