# PR #2408 Wave 3 subsystems — Verification Results

> Date: 2026-10-14
> PR: #2408 E7 Wave 3 course subsystems (`e7-wave3-subsystems`)
> Head: `6417575bed5`
> Base: master `98e8d5ad493`
> Runner: Playwright checklist-as-code (`browser-acceptance-harness`)
> Checklist: `checklists/pr-2408.yml` — **7 surfaces, all gates**

## 1. What was exercised

153 files, +1,510/−467. `text_type`, `list()` around dict views, `six.moves`,
and `BytesIO` swaps in capa, xmodule, courseware, grades, CSV, discussion,
and Studio. On the Python 2.7 m5-fixed devstack these are no-ops if they are
correct, so a surface proves "no crash" only when it also passes on master.

Local mount: `DEVSTACK_WORKSPACE=/Users/noahwang/workspace/hawthorn`,
`PLATFORM_MOUNT=.../platform-e7-wave3`, then the same checklist on
`PLATFORM_MOUNT=.../platform` (master). `docker compose -f docker-compose.yml
-f docker-compose-pr.yml up -d --no-deps lms studio`. The wave3 worktree
needed `setup.py egg_info` (platform + `common/lib/*`). `enable_devstack.sh`
appended the harness `FEATURES` block to both trees; those edits were
reverted after the run. The devstack was remounted to
`platform-e7-wave1-startup`, which is what it was running before this run.

## 2. Results

### 2026-10-14 — e7-wave3-subsystems `6417575bed5` — 7/7 passed (8.2s)

| # | Surface | Result | Role |
|---|---------|:---:|------|
| 1 | `GET /heartbeat` → 200 | pass | gate |
| 2 | `GET /dashboard` → 200, body contains `Copyright` and `Foundever` | pass | gate |
| 3 | `GET /courses/{course_key}/about` → 200, body contains `QA Acceptance Test` | pass | gate |
| 4 | `GET /courses/{course_key}/course/` → 200, body contains the title and course key | pass | gate |
| 5 | `GET /courses/{course_key}/progress` → 200 | pass | gate |
| 6 | `GET /courses/{course_key}/courseware` → 200 | pass | gate |
| 7 | Studio `GET /home/` → 200 | pass | gate |

### 2026-10-14 — master `98e8d5ad493` — 7/7 passed (9.5s)

Same seven surfaces. Every surface passes on both trees, so none of them is
a discriminator.

## 3. Not claimed

- Discussion `GET /courses/{course_key}/discussion/forum/` was not run.
  `edx.devstack.forum` is stopped. Wave 2 already saw the maintenance path
  500 (`Fragment()` on an `HttpResponse`).
- Dashboard course cards do not render for org `QA` on `localhost`: the site
  `course_org_filter` treats `qacert` as having no visible enrollments, so
  `_dashboard_course_listing.html` and `_dashboard_last_activity.html` are
  not executed. The footer template is.
- Sysadmin and instructor CSV writers, edxnotes service calls, word cloud,
  video transcripts, and vertical validation were not hit. The fixture course
  has no such block, and the CSV path runs only on export.

## 4. Rerun (same checklist, same heads)

2026-10-14 later the same day. Devstack was on `platform-e7-wave1-startup`
before the rerun. `PLATFORM_MOUNT` was switched to `platform-e7-wave3`
(`6417575bed5`), `enable_devstack.sh` appended the harness block, fixtures
were re-provisioned (`PROVISION_OK`), then the same `pr-2408.yml` ran.
Master `98e8d5ad493` was mounted and enabled the same way for the control.

| Tree | Result |
|---|---|
| `e7-wave3-subsystems` `6417575bed5` | 7/7 passed (9.1s) |
| master `98e8d5ad493` | 7/7 passed (14.0s) |

Same seven gates. Still no discriminator. After the run the harness blocks
were reverted on both trees and LMS/Studio were remounted to
`platform-e7-wave1-startup`. Heartbeat and Studio `/signin` both returned 200.
