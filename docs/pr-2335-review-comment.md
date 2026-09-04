## Browser Acceptance Testing — grades v0 API gate added

Follow-up to the 2026-07-21 3-surface run. Checklist now has **4 gates**. Ran against local devstack with `py3-m5-grades` mounted at HEAD `de00369e7e2`.

### Results (2026-09-03)

| # | Surface | py3-m5-grades | Role |
|---|---------|:---:|------|
| 1 | LMS `/` | ✅ 200 | gate |
| 2 | `/dashboard` | ✅ 200 | gate |
| 3 | Studio `/home/` | ✅ 200 | gate |
| 4 | `GET /api/grades/v0/course_grade/{course_key}/users/?username=qacert` (`request: true`) | ✅ 200 | gate |

**4/4 green (7.0s).** Surface 4 was 103ms.

Surface 4 body:

```json
[{"username":"qacert","letter_grade":null,"percent":0.0,"course_key":"course-v1:QA+Acceptance+Test","passed":false}]
```

### Why the API surface

The July dashboard gate only proves LMS HTML still renders. This PR's `text_type(course_id)` / `CourseGradeFactory` path is the grades stack, not the dashboard template.

v0 `UserGradeView` is session-auth and allows a learner to read her own grade, so `/auto_auth` as `qacert` is enough. v1 needs JWT `grades:read` and was not used.

`request: true` is required: `page.goto` drops `Accept` and would fetch HTML, making JSON field asserts vacuous.

Progress HTML is still excluded — the QA fixture course has no graded subsections, so `_progress` returns Http404.

This remains a **gate** (Py3 compat, no removal). Master was not re-run for surface 4; surfaces 1–3 already passed on both trees on 2026-07-21.

### Checklist

```yaml
# platform-browser-acceptance-harness/.claude/skills/browser-acceptance/checklists/pr-2335.yml
pr: 2335
surfaces: 4 (all gates — Py3 migration, no removals)
```

Full verification log: `devstack/docs/pr-2335-verification.md`
