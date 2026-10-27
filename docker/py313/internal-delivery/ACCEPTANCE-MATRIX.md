# Internal delivery acceptance matrix

Latest replay: delivery55. Exact inputs: platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack `4af117ba9d678ce077d3e38a855d136dd587e97f`, theme `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, runtime image `sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`, Python 3.13.14, native linux/arm64. Config SHA256 `22a79e2f77013309e0aafe858eb0eda67270df8e66c65e8bfa77d4a85cf1ddea`. Evidence root: `/Users/noahwang/workspace/hawthorn/py313-delivery55-evidence/`. Results apply only to the named replay.

| Scenario | Command / expected behavior | Delivery53 | Delivery54 | Delivery55 | Evidence |
| --- | --- | --- | --- | --- | --- |
| D0 paired source and fresh resource isolation | `run.py preflight`, `prepare`, `create`; exact commits, frozen-source contract, unique resources and ports | PASS | PASS | PASS | delivery55 `preflight.json`, `export.txt`, `commands.jsonl`, `input-preflight.txt` |
| D1 complete dependency closure | `run.py install`; full frozen lock, no dependency bypass, `uv pip check`, installed source bytes match | PASS: 315 | FAIL: lxml compiler OOM | PASS: 315, check, all 20 sources | delivery53/54/55 `install.txt`; delivery55 `installed-source-identity.txt` |
| D3 new development schema | `replay_after_install.py schema`; initialize empty run-scoped SQL database with local-model-sync; audit catalog | PASS: 149 apps/316 models/tables, 0 migration rows | NOT RUN | PASS: 149 apps/316 models/tables, 0 migration rows | delivery55 `initialize-schema.txt` |
| LMS/CMS settings checks | `manage.py lms/cms check` through registered replay settings | PASS with warnings | NOT RUN | PASS with warnings | delivery55 `lms-check.txt`, `cms-check.txt` |
| Theme and plugin source staging | Verify exact theme SHA and prepare 163 committed files | PASS | PRECHECK PASS | PASS | delivery55 `stage-theme.txt`, `saml-contract.txt` |
| npm and XModule asset build | `npm ci`; run `build_xmodule_assets.py` under LMS settings | PASS | NOT RUN | PASS | delivery55 `npm-ci.txt`, `xmodule-assets.txt` |
| Full frontend/theme/Webpack/locale/static phase | `replay_after_install.py assets`; build all runtime resources and collect LMS/CMS locale/static | PASS in delivery53, font 404 observed | NOT RUN | FAIL: Webpack exit 137 during source maps; diagnostic no-source-map Webpack produced 120 chunks each but is not a full-phase pass | delivery55 `frontend-assets.txt`, `webpack-capped-heap-3g-diagnostic.txt`, `webpack-capped-heap-1536m-diagnostic.txt`, `webpack-512m-memory-diagnostic.txt`, `webpack-no-source-maps-2g-diagnostic.txt`, `verify-webpack-no-source-maps.txt` |
| LMS/CMS browser login and rendered resources | Browser sign-in; inspect pages, console, network and localized resources | PARTIAL | NOT RUN | NOT RUN | Final paired replay required |
| Studio course authoring | Browser create/edit course and content; staff access only | PASS | NOT RUN | NOT RUN | delivery53 browser evidence only |
| Delayed publish and private draft | Wait >60s before first publish; unpublished draft denied to ordinary learners; published content available | NOT RUN | NOT RUN | NOT RUN | Must capture timestamps and learner responses on final replay |
| Learner published-content and completion | Ordinary enrolled learner reads correct published content, completes block, sees progress and course home | PARTIAL: course home HTTP 500 | NOT RUN | NOT RUN | delivery53 failure retained; verify platform fix in final replay |
| Role and organization access matrix | Anonymous, unenrolled, learner, staff, cross-org allow/deny | PARTIAL | NOT RUN | NOT RUN | Earlier ES permission-filter checks are partial only |
| Real Mongo/GridFS asset CRUD | Create/read/update/delete, sort/page/MIME; compare HTTP and SQL state | PARTIAL: create/read/list/filter passed; update/delete and cross-store consistency open | NOT RUN | NOT RUN | delivery53 GridFS record; repeat final |
| Published-course search and organization isolation | Publish through real broker/worker path; index and find only within permitted org | FAIL: worker success without course document | NOT RUN | NOT RUN | delivery52 worker/search failure retained; repeat final |
| Broker/worker business result | Enqueue via product workflow, observe actual broker delivery and persisted business result | PARTIAL: task acknowledged without indexed course | NOT RUN | NOT RUN | delivery52 worker/index evidence; repeat final |
| Core LT/File/SCORM/ILT workflows | Real author/read/upload/state operations and role denials with registered plugins | NOT RUN | NOT RUN | NOT RUN | Final replay required |
| Restart persistence | Snapshot course, asset, learner state; restart only owned services; verify persistence | NOT RUN | NOT RUN | NOT RUN | Final replay required |
| D4 independent checkout rebuild | New checkout follows committed instructions without old volumes, venv or author-only path | NOT RUN | NOT RUN | NOT RUN | Same-host limitation must be explicit if applicable |
| D5 local candidate and publication boundary | Exact paired commits, portable inputs, matrix, clean worktrees; no push until authorized | NOT RUN | NOT RUN | NOT RUN | No push/PR performed or authorized |

## Failure and repair history

- Delivery54 D1 failed with `cc1` killed while compiling lxml. See `/Users/noahwang/workspace/hawthorn/py313-delivery54-evidence/install.txt`.
- Delivery55 D1 and fresh schema passed. Its standard frontend asset phase failed with exit 137 during Webpack source-map generation; the exact failed command and interval are in `commands.jsonl`, and `frontend-assets.txt` preserves the kill. Do not treat the separate Webpack diagnostic as completion of `replay_after_install.py assets`.
- A devstack installer change to cap native build optimization is commit `4af117ba9d678ce077d3e38a855d136dd587e97f`. The Webpack memory/source-map fix is commit `0f4822593812682d435d9e25d1be7a604b17ceb3`. The fix requires a fresh complete replay.
- Delivery53 learner completion passed but course home returned HTTP 500. Platform fix `7962745ac4d0966442498326b1dad25696ea4c6f` must be reverified in the final learner browser flow.
- Delivery52 worker reported success without a searchable published course document. This failure remains open until the actual product indexing/search path passes.

Update this matrix and `STATUS.md` after each meaningful gate. Keep failed logs and later fix evidence side by side; never overwrite one run or promote earlier partial evidence to a final pass.
