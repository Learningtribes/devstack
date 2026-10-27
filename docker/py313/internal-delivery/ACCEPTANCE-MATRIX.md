# Internal delivery acceptance matrix

Historical matrix: delivery53–56. The current run-scoped results for delivery57/58 follow the table and are distinct from this baseline. Each result applies only to its named replay.

| Scenario | Command / expected behavior | Delivery53 | Delivery54 | Delivery55 | Delivery56 | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| D0 paired source and fresh resource isolation | `run.py preflight`, `prepare`, `create`; exact commits, frozen-source contract, unique resources/ports | PASS | PASS | PASS | PASS | delivery56 `preflight.json`, `export.txt`, `commands.jsonl`, `input-preflight.txt` |
| D1 complete dependency closure | `run.py install`; full frozen lock, no dependency bypass, `uv pip check`, source bytes match | PASS: 315 | FAIL: lxml compiler OOM | PASS: 315, checks, 20 sources | PASS: 315, checks, 20 sources | Each run's `install.txt`; delivery56 `installed-source-identity.txt` |
| D3 new development schema | `replay_after_install.py schema`; fresh local-model-sync and catalog audit | PASS: 149 apps/316 models/tables, 0 migration rows | NOT RUN | PASS: 149/316/316, 0 rows | PASS: 149/316/316, 0 rows | delivery56 `initialize-schema.txt` |
| LMS/CMS settings checks | Registered `manage.py lms/cms check` | PASS with warnings | NOT RUN | PASS with warnings | PASS with warnings | delivery56 `lms-check.txt`, `cms-check.txt` |
| Theme and plugin source staging | Verify theme SHA and prepare committed theme/plugin inputs | PASS | PRECHECK PASS | PASS | PASS | delivery56 `stage-theme.txt`, `saml-contract.txt` |
| npm and XModule asset build | `npm ci`; run `build_xmodule_assets.py` under LMS | PASS | NOT RUN | PASS | PASS | delivery56 `npm-ci.txt`, `xmodule-assets.txt` |
| Full frontend/theme/Webpack/locale/static phase | `replay_after_install.py assets`; build all resources and collect both systems | PASS in delivery53, font 404 observed | NOT RUN | FAIL: Webpack exit 137 | PASS: 120 chunks/login bundle on both systems; locale/static exited 0 | delivery55 failure; delivery56 `frontend-assets.txt`, `webpack-stats-audit.txt`, locale/static logs |
| LMS/CMS browser login and rendered resources | Browser sign-in; inspect pages, console, network, localization | PARTIAL | NOT RUN | NOT RUN | PARTIAL: login/course rendering worked; Studio font 404 remains open | delivery56 browser session; assets evidence above |
| Studio course authoring | Browser create/edit course/content; staff access only | PASS | NOT RUN | NOT RUN | PASS: course created, edited, published by course instructor without Django staff/superuser | delivery56 browser session; `delivery56-course-roles03.txt` |
| Delayed publish and private draft | First publish after >60s; draft denied to learners; publication then visible | NOT RUN | NOT RUN | NOT RUN | PARTIAL: published course visible; draft title visible while body withheld; exact first-publish interval not yet proven | `delivery56-course-publish-audit02.txt`, `delivery56-courseware-search-lms01.txt`; add timestamp audit |
| Learner content and completion | Enrolled ordinary learner reads content, completes block, sees progress/course home | PARTIAL: course home HTTP 500 | NOT RUN | NOT RUN | PASS browser path reported: learner read published content and reached 100% progress; capture durable state probe in final replay | delivery56 browser session; `completion-tracking.txt` |
| Role and organization access matrix | Anonymous, unenrolled, learner, staff, cross-org allow/deny | PARTIAL | NOT RUN | NOT RUN | PARTIAL: targeted LMS/CMS search-route permissions passed; product content search still returns zero | `delivery56-search-permissions-lms01.txt`, `delivery56-search-permissions-cms01.txt`, `delivery56-product-search-worker01.txt` |
| Real Mongo/GridFS asset CRUD | Create/read/update/delete, sort/page/MIME; compare HTTP and SQL | PARTIAL: create/read/list/filter passed | NOT RUN | NOT RUN | PASS: create/read/update/delete, sort/page/MIME and preservation checks | `delivery56-gridfs-crud01.txt` |
| File storage | Real provider reads/writes text and bytes and checks expiration behavior | NOT RUN | NOT RUN | NOT RUN | PASS | `delivery56-file-storage01.txt` |
| Published search and organization isolation | Product worker indexes published content; LMS learner search returns it; other org denied | FAIL: no document | NOT RUN | NOT RUN | FAIL: worker indexed six course/courseware docs, but LMS content endpoint returned 0; CMS catalog search also returned 0 | `delivery56-product-search-index01.txt`, `delivery56-product-search-worker01.txt`, `delivery56-courseware-search-lms01.txt`; diagnosis `delivery56-search-filter-proof01.txt`; source fix pending fresh replay |
| Broker/worker business result | Enqueue through product workflow; prove broker delivery and persisted result | PARTIAL: task ack without index | NOT RUN | NOT RUN | PARTIAL: task `37157cfc-5a58-49c2-aea6-fa7972bcf9ee` completed and indexed; search API assertion failed | `delivery56-product-search-worker01.txt` |
| SCORM authoring, upload, learner state and isolation | Draft-branch component, staff upload; role denials; learner commits and per-user state | NOT RUN | NOT RUN | NOT RUN | FAIL: staff upload 500; probe component existed only on published branch; anonymous/learner/other-org denials returned | `delivery56-scorm-routed01.txt`, `delivery56-scorm-branch-audit01.txt`, `delivery56-scorm-state01.txt` |
| ILT staff enrollment, attendance, grading and learner isolation | Real ILT block and handler flow | NOT RUN | NOT RUN | NOT RUN | NOT RUN: no ILT block was created | Adapt run28 helper only after a unique draft-branch block exists; preserve old assertion failure |
| Restart persistence | Snapshot course/assets/learner state; restart owned services and verify | NOT RUN | NOT RUN | NOT RUN | NOT RUN | Run after passing business data is durable |
| D4 independent checkout rebuild | New checkout follows committed instructions without old volumes, venv or author paths | NOT RUN | NOT RUN | NOT RUN | NOT RUN | Must state same-host limitation, if applicable |
| D5 local candidate/publication boundary | Exact paired commits, portable inputs, clean worktrees; no push before authorization | NOT RUN | NOT RUN | NOT RUN | NOT RUN | No push/PR performed or authorized |

## Current replay updates

### Delivery58 — OrbStack resource failure

Inputs: platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack `77d6e8774017cbd70f8bbc8e8cd226d5fd5e2f59`, theme `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, runtime image `sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`, Python 3.13.14, native linux/arm64. Canonical config SHA256 `f454e0251a88d9e031b7dbf5352dc9ef3f0b747d368eecdd901e2fa0504bbdf9`; evidence root `/Users/noahwang/workspace/hawthorn/py313-delivery58-evidence/`.

| Scenario | Delivery58 result | Evidence |
| --- | --- | --- |
| D0 preflight/export/new resource isolation | PASS | `preflight.json`, `export.txt`, `create-network.txt`, `create-infra.txt`, `create-runtime.txt` |
| D1 locked install and source identity | PASS: 315 distributions, `uv pip check`, all 20 registered source trees | `install.txt`, `installed-source-identity.txt` |
| D3 new development schema and checks | PASS: local-model-sync; 149 apps, 316 models/tables, 0 historical migration rows; LMS/CMS checks exit 0 with warnings | `initialize-schema.txt`, `lms-check.txt`, `cms-check.txt` |
| D3 assets and static resources | PASS: npm, XModule, LMS/CMS Webpack 120 chunks each, both locale/static phases | `npm-ci.txt`, `xmodule-assets.txt`, `frontend-assets.txt`, `lms-locale-static.txt`, `cms-locale-static.txt` |
| D3 HTTP/login | FAIL infrastructure: login page rendered and HTTP 200, submit returned 500 because OOM-down MySQL made `mysql` unresolvable | `delivery58-service-oom.txt`, `/runtime/logs/lms-http.log` in owned container |
| D3 course, learner, permission and publication flows | NOT RUN | No valid authenticated browser path after MySQL OOM; delivery56 evidence does not carry over |
| D3 search, worker business result, storage, SCORM and ILT | BLOCKED by delivery58 Elasticsearch/MySQL OOM | `delivery58-service-oom.txt` |
| D3 restart persistence; D4 independent checkout; D5 local candidate | NOT RUN | Requires successful final paired replay |

Elasticsearch OOM-killed during initial service startup and again during one diagnosis start. MySQL was found OOM-killed, then started once and remained up during a short observation. OrbStack reported 16 GiB VM memory, about 590 MiB available, and nearly exhausted swap. Existing older-run resources were not changed. Retain all delivery58 resources and logs.

### Delivery59 — isolated engine replay preparation

The independent Docker Desktop daemon has an 8 GiB VM; it also contains unrelated project resources that remain untouched. An archive copied read-only from OrbStack retained all 15 runtime rootfs layer digests and image config. Desktop exposes imported runtime image ID `sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c`, distinct from OrbStack's local image ID. Archive SHA256: `20dbfe1562c1c49d5f1492e8094fd7040df09833942c94922de44d02129d3cbe`. The exact Desktop ID must be recorded in its config and selected-image audit. New ports, subnet, namespace, credentials, volumes and evidence path are being allocated; preflight/create/install have not run yet.

## Failure and repair history

- Delivery54 D1 failed when lxml's `cc1` process was OOM-killed; its install log remains unchanged.
- Delivery55 D1/schema/checks passed. Its full frontend asset command failed with exit 137; the exact command interval and output remain in `commands.jsonl` and `frontend-assets.txt`. Separate Webpack diagnostics do not count as a full asset-phase pass.
- Devstack commit `0f4822593812682d435d9e25d1be7a604b17ceb3` adds the 2 GiB Webpack heap cap and disables development source maps. Delivery56 is the fresh replay of this exact fix.
- Platform commit `7962745ac4d0966442498326b1dad25696ea4c6f` fixes the learner course-home template context; verify with the final learner browser path.
- Delivery52 search worker reported success without a searchable course document; retain as FAIL until final product-path search passes.
- Delivery56 product worker reported task success and populated Elasticsearch, but user-facing search returned zero. `delivery56-search-filter-proof01.txt` isolates an `exclude="archived"` marker sent as a required field that courseware documents do not contain: same query yields one result without the marker and zero with it. Devstack working-tree patch removes that catalog-only marker from `perform_search` and adds a regression test. Delivery56 stays FAIL; only a clean replay of the newly committed package can pass it.
- Delivery56 SCORM probe constructed its XBlock on the published branch, while Studio queried the draft branch. The staff upload 500 is retained, and it is not yet a valid product-path SCORM conclusion. Recreate through Studio/draft branch and repeat the whole role/state matrix.

Update this matrix and `STATUS.md` after each meaningful gate. Keep failed logs and later fix evidence side by side; never overwrite one run or promote earlier partial evidence to a final pass.
