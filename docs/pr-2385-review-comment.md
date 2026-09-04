## Browser Acceptance Testing — ✅ Verified

Ran a 6-surface Playwright checklist against local devstack with the `teams-split` worktree mounted. Master double-run proves 2 discriminators.

### Results (2026-09-04)

| # | Surface | Master | teams-split | Role |
|---|---------|:---:|:---:|------|
| 1 | `/courses/{course_key}/teams/` (`request: true`, `auth: none`) | ❌ 200 | ✅ 404 | **discriminator** |
| 2 | `/api/team/v0/teams/` (`request: true`, `auth: qacert`) | ❌ 400 | ✅ 404 | **discriminator** |
| 3 | LMS `/` | ✅ 200 | ✅ 200 | gate |
| 4 | `/dashboard` | ✅ 200 | ✅ 200 | gate |
| 5 | Studio `/home/` | ✅ 200 | ✅ 200 | gate |
| 6 | Studio `/program_team/` (`qastaff`) | ✅ 403 | ✅ 403 | gate (KEEP) |

**6/6 green on teams-split (5.1s). 2 discriminators proven (route-existence flip).**

### Discriminators

LMS Course Teams URLs are gated on `FEATURES['ENABLE_TEAMS']`, default **True**, so they are registered on master.

- Dashboard: unauthenticated `request: true` (opaque course key; `page.goto` would eat `+`). Master `login_required` 302 is followed to login 200; PR 404.
- API: authenticated GET with no `course_id` is 400 on master (`course_id must be provided`) and 404 after the include is deleted. No `teams_enabled` fixture.

YAML lists the `auth: none` surface first. The runner shares one BrowserContext; `auth: none` after `qacert` still has learner cookies, and the QA fixture course 404s `TeamsDashboardView` on master too (vacuous).

### Gates

LMS home + dashboard prove the deleted Course Teams app does not crash imports. Studio home proves CMS boots with `program_enrollments` imports. `/program_team/` 403 with `qastaff` proves the KEEP Studio view is still routed (403 is `STUDIO_EDIT_CONTENT` without a program UUID; 404 would mean the page was dropped).

### Excluded

No CourseTeam admin. Instructor "team" column and the Teams course tab need Mongo `teams_enabled` / a stored tab. CMS `/api/team/v0/programadmins/` without an id 500s (list view reads `kwargs['id']`).

Full log: `devstack/docs/pr-2385-verification.md`
