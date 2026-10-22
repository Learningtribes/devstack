# PR #2407 Wave 2 import and text — Verification Results

> Date: 2026-10-14
> PR: #2407 E7 Wave 2 small Track E (`e7-wave2-small`)
> Head: `f652ed90893`
> Base: master `98e8d5ad493`
> Runner: Playwright checklist-as-code (`browser-acceptance-harness`)
> Checklist: `checklists/pr-2407.yml` — **8 surfaces, all gates**

## 1. What was exercised

27 files, +305/−79. Relative imports, `list()` around dict views, `text_type` /
`BytesIO` / `six.moves` swaps. On the Python 2.7 m5-fixed devstack these are
no-ops if they are correct, so a surface proves "no crash" only when it also
passes on master.

Local mount: `DEVSTACK_WORKSPACE=/Users/noahwang/workspace/hawthorn`,
`PLATFORM_MOUNT=.../platform-e7-wave2`, then the same checklist on
`PLATFORM_MOUNT=.../platform` (master). `docker compose -f docker-compose.yml
-f docker-compose-pr.yml up -d --no-deps lms studio`. Fresh worktree needed
`setup.py egg_info` (platform + `common/lib/*`). `enable_devstack.sh` appended
the harness `FEATURES` block to both trees; those edits stay uncommitted and
are reverted after the run.

## 2. Results

### 2026-10-14 — e7-wave2-small `f652ed90893` — 8/8 passed (8.1s)

| # | Surface | Result | Role |
|---|---------|:---:|------|
| 1 | `GET /heartbeat` → 200 | pass | gate |
| 2 | `GET /u/qacert` → 200, body contains `qacert` | pass | gate |
| 3 | `GET /courses/{course_key}/bookmarks/` → 200, body contains `bookmark` | pass | gate |
| 4 | `GET /courses/{course_key}/search/` → 200 | pass | gate |
| 5 | `GET /courses/{course_key}/course/` → 200, body contains `QA Acceptance Test` | pass | gate |
| 6 | `GET .../course/welcome_message_fragment` → 204 | pass | gate |
| 7 | `GET /dashboard` → 200 | pass | gate |
| 8 | Studio `GET /home/` → 200 | pass | gate |

Shell on the same LMS process: `comment_client.thread.Thread`,
`comment_client.user.User`, and `CommentClientMaintenanceError` import.
`CourseTabPluginManager.get_tab_types()` returned
`courseware,course_info,syllabus,progress,discussion,edxnotes,...`.
`CourseToolsPluginManager` reported 3 tools.

### 2026-10-14 — master `98e8d5ad493` — 8/8 passed

Same eight surfaces. Studio `/home/` failed once with `ERR_EMPTY_RESPONSE`
while CMS was still binding :18010 after restart, then passed (3.4s) once
`/signin` returned 200. Every surface passes on both trees, so none of them
is a discriminator.

## 3. Not claimed

- Discussion `GET /courses/{course_key}/discussion/forum/` returned 500 on
  wave2. `edx.devstack.forum` is stopped. The view caught
  `CommentClientMaintenanceError: service disabled`, then
  `render_to_fragment` did `Fragment(render_to_response(...))` and raised
  `AssertionError`. That is the maintenance path, not an import failure.
- LTI signature helpers, `StaticContent` thumbnail `BytesIO`, profile-image
  upload, and `ApiCustomPagination` (`/api/extended/` is OAuth2) were not hit.
- Welcome 204 means the course has no welcome HTML, so `text_type(course_key)`
  on the dismiss URL did not run. The relative `course_updates` import did.
