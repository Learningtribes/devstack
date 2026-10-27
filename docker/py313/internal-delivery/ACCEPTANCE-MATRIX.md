# Internal delivery acceptance matrix

Current replay: delivery56, config SHA256 `3b0ccb3301ea3456a62eedbcb56303e3ff770928d7c4603c16454c6cde06f4d4`. Exact inputs: platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack `bb22dee9eb4108291f341acfd576b72152f241eb`, theme `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, runtime image `sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`, Python 3.13.14, native linux/arm64. Evidence root: `/Users/noahwang/workspace/hawthorn/py313-delivery56-evidence/`. Results apply only to the named replay.

| Scenario | Command / expected behavior | Delivery53 | Delivery54 | Delivery55 | Delivery56 | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| D0 paired source and fresh resource isolation | `run.py preflight`, `prepare`, `create`; exact commits, frozen-source contract, unique resources/ports | PASS | PASS | PASS | PASS | delivery56 `preflight.json`, `export.txt`, `commands.jsonl`, `input-preflight.txt` |
| D1 complete dependency closure | `run.py install`; full frozen lock, no dependency bypass, `uv pip check`, source bytes match | PASS: 315 | FAIL: lxml compiler OOM | PASS: 315, checks, 20 sources | PASS: 315, checks, 20 sources | Each run's `install.txt`; delivery56 `installed-source-identity.txt` |
| D3 new development schema | `replay_after_install.py schema`; fresh local-model-sync and catalog audit | PASS: 149 apps/316 models/tables, 0 migration rows | NOT RUN | PASS: 149/316/316, 0 rows | PASS: 149/316/316, 0 rows | delivery56 `initialize-schema.txt` |
| LMS/CMS settings checks | Registered `manage.py lms/cms check` | PASS with warnings | NOT RUN | PASS with warnings | PASS with warnings | delivery56 `lms-check.txt`, `cms-check.txt` |
| Theme and plugin source staging | Verify theme SHA and prepare committed theme/plugin inputs | PASS | PRECHECK PASS | PASS | PASS | delivery56 `stage-theme.txt`, `saml-contract.txt` |
| npm and XModule asset build | `npm ci`; run `build_xmodule_assets.py` under LMS | PASS | NOT RUN | PASS | RUNNING | delivery56 `npm-ci.txt`, `xmodule-assets.txt` |
| Full frontend/theme/Webpack/locale/static phase | `replay_after_install.py assets`; build all resources and collect both systems | PASS in delivery53, font 404 observed | NOT RUN | FAIL: Webpack exit 137 | RUNNING with 2 GiB heap and no dev source maps | delivery55 failure and diagnostic logs; delivery56 `frontend-assets.txt` and locale/static logs pending |
| LMS/CMS browser login and rendered resources | Browser sign-in; inspect pages, console, network, localization | PARTIAL | NOT RUN | NOT RUN | NOT RUN | Run after assets and service startup |
| Studio course authoring | Browser create/edit course/content; staff access only | PASS | NOT RUN | NOT RUN | NOT RUN | Final replay required |
| Delayed publish and private draft | First publish after >60s; draft denied to learners; publication then visible | NOT RUN | NOT RUN | NOT RUN | NOT RUN | Capture timestamps and learner responses |
| Learner content and completion | Enrolled ordinary learner reads content, completes block, sees progress/course home | PARTIAL: course home HTTP 500 | NOT RUN | NOT RUN | NOT RUN | Verify platform fix in final replay |
| Role and organization access matrix | Anonymous, unenrolled, learner, staff, cross-org allow/deny | PARTIAL | NOT RUN | NOT RUN | NOT RUN | Earlier selected filters are partial only |
| Real Mongo/GridFS asset CRUD | Create/read/update/delete, sort/page/MIME; compare HTTP and SQL | PARTIAL: create/read/list/filter passed | NOT RUN | NOT RUN | NOT RUN | Final replay required |
| Published search and organization isolation | Real product worker indexes published course; allowed org finds it, other org denied | FAIL: no document | NOT RUN | NOT RUN | NOT RUN | Delivery52 failure retained; final replay required |
| Broker/worker business result | Enqueue through product workflow; prove broker delivery and persisted result | PARTIAL: task ack without index | NOT RUN | NOT RUN | NOT RUN | Final replay required |
| Core LT/File/SCORM/ILT workflows | Real author/read/upload/state operations and role denials | NOT RUN | NOT RUN | NOT RUN | NOT RUN | Final replay required |
| Restart persistence | Snapshot course/assets/learner state; restart owned services and verify | NOT RUN | NOT RUN | NOT RUN | NOT RUN | Final replay required |
| D4 independent checkout rebuild | New checkout follows committed instructions without old volumes, venv or author paths | NOT RUN | NOT RUN | NOT RUN | NOT RUN | Must state same-host limitation, if applicable |
| D5 local candidate/publication boundary | Exact paired commits, portable inputs, clean worktrees; no push before authorization | NOT RUN | NOT RUN | NOT RUN | NOT RUN | No push/PR performed or authorized |

## Failure and repair history

- Delivery54 D1 failed when lxml's `cc1` process was OOM-killed; its install log remains unchanged.
- Delivery55 D1/schema/checks passed. Its full frontend asset command failed with exit 137; the exact command interval and output remain in `commands.jsonl` and `frontend-assets.txt`. Separate Webpack diagnostics do not count as a full asset-phase pass.
- Devstack commit `0f4822593812682d435d9e25d1be7a604b17ceb3` adds the 2 GiB Webpack heap cap and disables development source maps. Delivery56 is the fresh replay of this exact fix.
- Platform commit `7962745ac4d0966442498326b1dad25696ea4c6f` fixes the learner course-home template context; verify with the final learner browser path.
- Delivery52 search worker reported success without a searchable course document; retain as FAIL until final product-path search passes.

Update this matrix and `STATUS.md` after each meaningful gate. Keep failed logs and later fix evidence side by side; never overwrite one run or promote earlier partial evidence to a final pass.
