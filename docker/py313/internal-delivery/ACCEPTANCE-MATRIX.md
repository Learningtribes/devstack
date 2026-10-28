# Internal delivery acceptance matrix

Historical matrix: delivery53–56. Run-scoped results for later deliveries follow the table and are distinct from this baseline. Each result applies only to its named replay.

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

### Delivery64 — dependency/schema/assets pass; Elasticsearch OOM

Inputs: platform `36d1a28ec7dfe85c6036fd52bd82c926fc2492ec`, devstack
`0bf5de98e2cd311d39a99af11a34b2a3fc2e9706`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, native linux/arm64, Python
3.13.14. Dedicated engine/context: `py313-delivery64`; runtime image ID
`sha256:6d6227966492c5c5af9c02c10b71b3c6bc37810f1e4c0ff22affe2fb7e5ccfb4`.
Image build log is host-private at
`/Users/noahwang/workspace/hawthorn/py313-delivery64/private/runtime-image-build.txt`.
Raw config SHA256 `a6a54f05818e0f2087b5d0b36a16e67f5b1a4793977d625c998371d326e38ba8`;
canonical config hash `557a5c89e0777c71435e34428203651b114edbe23257b385208e502846c748e1`.
Resources are reserved under the `delivery64` identity, network
`172.29.64.0/24`, ports 19880/19890, database `py313_rebuild_delivery64`, and
Mongo/cache/search/queue namespace `delivery64`. Evidence root will be
`/Users/noahwang/workspace/hawthorn/py313-delivery64-evidence/`.

| Scenario | Delivery64 result | Evidence |
| --- | --- | --- |
| D0 paired source and resource preflight | PASS initially; first `prepare` retry FAIL closed before creating outputs because the checkpoint documentation was uncommitted; retry after local commit | `preflight.json`, `prepare-attempt01-uncommitted-checkout.txt`; runner canonical config hash |
| Runtime image build | PASS: committed `docker/py313/Dockerfile`, `internal-delivery` target; native arm64, Python 3.13.14, uv 0.11.23, Node 16.20.2 | host-private build log and image inspect |
| D1 full locked install and registered source identity | PASS: 315 distributions, `uv pip check`, all 20 registered source trees | `install.txt`, `installed-source-identity.txt` |
| D3 fresh schema/settings checks | PASS: 149 apps, 316 models including M2M, 316 tables, zero historical migration rows; LMS/CMS checks exit 0 with warnings | `initialize-schema.txt`, `lms-check.txt`, `cms-check.txt` |
| D3 Elasticsearch/product search | FAIL infrastructure: Elasticsearch exit 137/OOMKilled during startup | `delivery64-elasticsearch-oom.txt` |
| D3 theme, npm, XModule, frontend, locale/static assets | PASS: both Webpack builds emitted 120 chunks; locale/static commands exited 0 | `stage-theme.txt`, `npm-ci.txt`, `xmodule-assets.txt`, `frontend-assets.txt`, `lms-locale-static.txt`, `cms-locale-static.txt` |
| D3 targeted Studio regression tests | PASS: Studio Logs template and course-author reindex tests, 1/1 each | `delivery64-studio-logs.txt`, `delivery64-reindex-author.txt` |
| D3 browser/core business | NOT RUN; Elasticsearch failure blocked the required live search path | repeat on fresh D65 |
| D4 independent checkout rebuild | NOT RUN | requires final paired candidate |
| D5 local candidate | NOT RUN | no push or PR |

D64 resources were created on its dedicated engine and remain preserved. Its
Elasticsearch container exited 137/OOMKilled; do not restart or reuse D64
resources for acceptance. Delivery63 is a separate failed attempt.

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

### Delivery59 — install/assets pass; Studio publish authorization failure

Inputs: platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack
`88cdf21e1423d0ae91f9776dd456722d1710de1b`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, runtime image ID
`sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c`;
Python 3.13.14, native linux/arm64, canonical config hash
`27e3812bd2e48c1c2ab5c4a3e3d466972ffa08c6a4cd8e6c64b4f79e4c48b3e2`.
Fresh resource identity: Docker Desktop network `py313-delivery59-network`
(`10.254.59.0/24`), loopback ports 19380/19390, SQL database
`py313_rebuild_delivery59`, Mongo and service namespaces `py313_delivery59`,
and dedicated labeled volumes. Evidence:
`/Users/noahwang/workspace/hawthorn/py313-delivery59-replay-evidence/`.

| Scenario | Delivery59 result | Evidence |
| --- | --- | --- |
| D0 source/resource isolation | PASS | `preflight.json`, `export.txt`, `commands.jsonl`, `input-preflight.txt`, labeled resource commands |
| D1 complete locked install | PASS: 315 distributions, `uv pip check`, all 20 registered source trees byte-identical | `install.txt`, `installed-source-identity.txt` |
| D3 fresh development schema and LMS/CMS checks | PASS: 149 apps, 316 models/tables, zero historical migration rows; checks exited 0 with warnings | `initialize-schema.txt`, `lms-check.txt`, `cms-check.txt` |
| D3 theme/plugin/static assets | PASS: npm/XModule, 120 Webpack chunks per system, locale/static | `stage-theme.txt`, `npm-ci.txt`, `xmodule-assets.txt`, `frontend-assets.txt`, `lms-locale-static.txt`, `cms-locale-static.txt` |
| D3 browser sign-in and authoring | PARTIAL: login, course creation/edit and ordinary learner enrollment passed; release modal did not complete | `delivery59-course-state.txt`, `delivery59-author-plugins-enrollment02.txt`, protected CMS HTTP log |
| D3 Studio publish search-reindex request | **FAIL 403** for a non-platform-admin course instructor; retry also 403 | `commands.jsonl`, protected CMS HTTP log; state retained in run evidence |
| D3 learner publication, draft privacy, permission/org matrix | NOT RUN on successfully completed publication | Repeat on delivery60 |
| D3 real search/worker business result | NOT RUN | Repeat on delivery60; delivery56's indexed docs but zero search results remain separate historical FAIL |
| D3 GridFS/File CRUD, SCORM, ILT, restart persistence | NOT RUN on this replay | Execute against delivery60's final data |
| D4 independent checkout rebuild | NOT RUN | Requires final paired source and instructions |
| D5 local candidate | NOT RUN | No push/PR |

Diagnosis: `course_search_index_handler` rejected the user by platform role
before calling `reindex_course_and_check_access`, which already checks the
target course's author permissions. Platform commit
`8f31fa2d9eaa4e1deeb2762b143b536a338d9f02` removes this redundant gate and adds
own-course instructor / unrelated-course denial coverage. Delivery59 remains
immutable failure history; do not patch or restart its runtime.

### Delivery61 — runtime gates pass; legacy test import failed

Inputs: platform `8f31fa2d9eaa4e1deeb2762b143b536a338d9f02`, devstack
`4f085f413ff60d407680ed527f9f27f3d2011aa3`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, Docker Desktop runtime image ID
`sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c`;
Python 3.13.14, native linux/arm64, canonical config hash
`b5b5904449d403f61878d0bccc035a98916bb58cd4296b84b7bb561a311b6faa`.
Resources: network `py313-delivery61-network` (`10.254.61.0/24`), ports
19580/19590, SQL `py313_rebuild_delivery61`, Mongo/service namespaces
`py313_delivery61`, dedicated volumes. Evidence:
`/Users/noahwang/workspace/hawthorn/py313-delivery61-evidence/`.

| Scenario | Delivery61 result | Evidence |
| --- | --- | --- |
| D0 paired source/resource isolation | PASS | `preflight.json`, `export.txt`, `commands.jsonl`, labeled resources |
| D1 full locked installation/source identity | PASS: 315 distributions, `uv pip check`, all 20 source trees | `install.txt`, `installed-source-identity.txt` |
| D3 fresh schema and LMS/CMS checks | PASS: 149 apps, 316 models/tables, zero historical migration rows; checks with recorded warnings | `initialize-schema.txt`, `lms-check.txt`, `cms-check.txt` |
| D3 resource/asset build | PASS: npm/XModule, 120 Webpack chunks per system, locale/static | `npm-ci.txt`, `xmodule-assets.txt`, `frontend-assets.txt`, locale/static logs |
| D3 targeted CMS reindex regression | **FAIL collection/import**: legacy module imports missing test-only `factory_boy` before any test assertion | `cms-course-reindex-auth01.txt`, `commands.jsonl` |
| D3 browser, publish, learner, permission/org, search/worker, storage, SCORM/ILT, restart | NOT RUN | Re-run on delivery62 after focused test passes |
| D4 independent checkout | NOT RUN | Requires final paired source |
| D5 local candidate | NOT RUN | No push/PR |

The runtime dependency lock intentionally remains the complete delivery runtime set; this failure identifies a test-selector issue. Platform `aed8961d6920954068949afbcf34440ee94bd4cd` adds a focused test without factory fixtures. Delivery61 is not candidate evidence and no resources are reused.

### Delivery60 — schema/assets pass; host test-dispatch failure

Inputs: platform `8f31fa2d9eaa4e1deeb2762b143b536a338d9f02`, devstack
`8f5f6e97d27126c26eb6e56e0a9b684d785609a4`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, runtime image ID
`sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c`;
Python 3.13.14, native linux/arm64, canonical config hash
`f979f31e08459fdb2a23ac79918a1c0f11667740147b180eb0e02131d1c75ce9`.
Fresh resource identity: network `py313-delivery60-network`
(`10.254.60.0/24`), loopback ports 19480/19490, SQL
`py313_rebuild_delivery60`, Mongo/service namespaces `py313_delivery60`, and
new labeled volumes. Evidence:
`/Users/noahwang/workspace/hawthorn/py313-delivery60-evidence/`.

| Scenario | Delivery60 result | Evidence |
| --- | --- | --- |
| D0 source/resource isolation | PASS | `preflight.json`, `export.txt`, `commands.jsonl`, labeled resources |
| D1 complete locked install/source identity | PASS: 315 distributions, `uv pip check`, 20 registered source trees | `install.txt`, `installed-source-identity.txt` |
| D3 fresh schema and checks | PASS: local-model-sync, 149 apps, 316 models/tables, zero historical migration rows; LMS/CMS checks exit 0 with warnings | `initialize-schema.txt`, `lms-check.txt`, `cms-check.txt` |
| D3 resources/assets | PASS: npm/XModule, 120 Webpack chunks per system, locale/static | `npm-ci.txt`, `xmodule-assets.txt`, `frontend-assets.txt`, locale/static logs |
| D3 targeted CMS course-author regression | **FAIL harness dispatch**: host runner raised `UnboundLocalError` before `capture()`; no Docker test process or test DB ran | `delivery60-test-action-failure.txt`, appended `commands.jsonl` |
| D3 browser/business/search/storage/SCORM/ILT/restart | NOT RUN | D60 is incomplete; use delivery61 final pair |
| D4 independent checkout | NOT RUN | Requires final paired source |
| D5 local candidate | NOT RUN | No push/PR |

The dispatch defect is corrected in devstack `47efd68399fceaf8e99d2cf577b7e5b47a6e80a9`, with 28 runner contract tests passing. Delivery60 remains immutable harness-failure history; no D60 container or volume is reused.

### Delivery62 — dependency/schema/assets pass; Studio Logs defect found

Inputs: platform `aed8961d6920954068949afbcf34440ee94bd4cd`, devstack
`66d1795f69677907baa441739ae4553b643ee511`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, Docker Desktop runtime image
`sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c`,
Python 3.13.14, native linux/arm64, canonical config hash
`fdd39103edab50348f7358e91fe3aade9138ebafc2d0c2fab1aa10899b2443c0`.
Network `py313-delivery62-network` (`10.254.62.0/24`), loopback ports
19680/19690, SQL `py313_rebuild_delivery62`, Mongo/service namespaces
`py313_delivery62`, dedicated volumes. Evidence:
`/Users/noahwang/workspace/hawthorn/py313-delivery62-evidence/`.

| Scenario | Delivery62 result | Evidence |
| --- | --- | --- |
| D0 source/resource isolation | PASS | `preflight.json`, `export.txt`, `commands.jsonl`, labeled resources |
| D1 full locked installation/source identity | PASS: 315 distributions, `uv pip check`, 20 registered source trees | `install.txt`, `installed-source-identity.txt` |
| D3 fresh schema/checks/assets | PASS: local-model-sync, 149 apps, 316 models/tables, zero historical migration rows; theme/npm/XModule/Webpack/locale/static pass | `initialize-schema.txt`, check and asset logs |
| D3 focused course-author reindex regression | PASS 1/1 | `cms-course-reindex-auth01.txt` |
| D3 Studio Logs rendering regression | FAIL first attempt (`NameError: Undefined`); after platform fix PASS 1/1 | `d62-studio-logs-template-test01.txt`, `d62-studio-logs-template-test02.txt` |
| D3 browser Studio Logs | FAIL 500 before the template fix | `d62-cms-http-log01.txt` |
| D3 Studio authoring and learner business flow | NOT RUN to completion; Create remained disabled | `d62-course-create-fields01.txt`, `d62-course-state02.txt` |
| D3 search/worker, real storage, SCORM/ILT, role/org matrix, restart | NOT RUN | Re-run on a fresh exact pair |
| D4 independent checkout; D5 local candidate | NOT RUN | Requires final exact pair |

### Delivery63 — OOM during search; candidate acceptance incomplete

Inputs: platform `36d1a28ec7dfe85c6036fd52bd82c926fc2492ec`, devstack
`66d1795f69677907baa441739ae4553b643ee511`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, Docker Desktop runtime image
`sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c`,
Python 3.13.14, native linux/arm64, canonical config hash
`79f361576a8844cb14411039bc9437e2cdd6758fcb4001e720a119d2a1da7679`.
Network `py313-delivery63-network` (`10.254.63.0/24`), loopback ports
19780/19790, SQL `py313_rebuild_delivery63`, Mongo/service namespaces
`py313_delivery63`, dedicated volumes. Evidence:
`/Users/noahwang/workspace/hawthorn/py313-delivery63-evidence/`.

| Scenario | Delivery63 result | Evidence |
| --- | --- | --- |
| D0 source/resource isolation | PASS | `preflight.json`, `export.txt`, `commands.jsonl` |
| D1 complete locked install/source identity | PASS: 315 distributions, `uv pip check`, all 20 registered source trees | `install.txt`, `installed-source-identity.txt` |
| D3 fresh schema, LMS/CMS checks and assets | PASS: 149 apps/316 models/tables, zero historical migration rows; both 120-chunk Webpack builds and locale/static pass | schema/check/asset logs |
| D3 Studio Logs and course-author reindex regression tests | PASS 1/1 each | `d63-studio-logs.txt`, `d63-reindex-author.txt` |
| D3 LMS/Studio browser sign-in | PASS | browser session evidence; `delivery63-cms-http-log.txt` |
| D3 Elasticsearch and CMS search | FAIL infrastructure: ES exited 137, OOMKilled; CMS `/course_search/` returned 500 due failed `elasticsearch` name resolution | `delivery63-elasticsearch-oom.txt`, `delivery63-cms-http-log.txt` |
| D3 create/edit/publish, learner/draft, role/org, worker/search result, storage, SCORM/ILT, restart | NOT RUN to completion; no course was created | run-scoped HTTP log and browser session |
| D4 independent checkout; D5 local candidate | NOT RUN | A new replay and independent rebuild are required |

Docker Desktop's VM had 8 GiB total and no free swap at the diagnostic snapshot;
the ES container was unbounded and its JVM heap was 256 MiB. This is an
infrastructure failure, not a product search assertion. No older run resource
was changed. Do not restart, patch or reuse delivery63.

## Failure and repair history

- Delivery54 D1 failed when lxml's `cc1` process was OOM-killed; its install log remains unchanged.
- Delivery55 D1/schema/checks passed. Its full frontend asset command failed with exit 137; the exact command interval and output remain in `commands.jsonl` and `frontend-assets.txt`. Separate Webpack diagnostics do not count as a full asset-phase pass.
- Devstack commit `0f4822593812682d435d9e25d1be7a604b17ceb3` adds the 2 GiB Webpack heap cap and disables development source maps. Delivery56 is the fresh replay of this exact fix.
- Platform commit `7962745ac4d0966442498326b1dad25696ea4c6f` fixes the learner course-home template context; verify with the final learner browser path.
- Delivery52 search worker reported success without a searchable course document; retain as FAIL until final product-path search passes.
- Delivery56 product worker reported task success and populated Elasticsearch, but user-facing search returned zero. `delivery56-search-filter-proof01.txt` isolates an `exclude="archived"` marker sent as a required field that courseware documents do not contain: same query yields one result without the marker and zero with it. Devstack working-tree patch removes that catalog-only marker from `perform_search` and adds a regression test. Delivery56 stays FAIL; only a clean replay of the newly committed package can pass it.
- Delivery56 SCORM probe constructed its XBlock on the published branch, while Studio queried the draft branch. The staff upload 500 is retained, and it is not yet a valid product-path SCORM conclusion. Recreate through Studio/draft branch and repeat the whole role/state matrix.

Update this matrix and `STATUS.md` after each meaningful gate. Keep failed logs and later fix evidence side by side; never overwrite one run or promote earlier partial evidence to a final pass.
