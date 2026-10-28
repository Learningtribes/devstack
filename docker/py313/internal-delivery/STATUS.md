# Python 3.13 internal delivery status

Updated: 2026-10-28 (Asia/Shanghai). Goal remains active. State: **local delivery candidate incomplete**.

## Latest replay: delivery63 (dependency/runtime gates pass; Elasticsearch OOM)

Delivery63 used platform `36d1a28ec7dfe85c6036fd52bd82c926fc2492ec`, devstack
`66d1795f69677907baa441739ae4553b643ee511`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, and Docker Desktop runtime image ID
`sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c`.
Target: native linux/arm64, Python 3.13.14, Django 5.2.13. Canonical config
SHA256 `79f361576a8844cb14411039bc9437e2cdd6758fcb4001e720a119d2a1da7679`;
evidence `/Users/noahwang/workspace/hawthorn/py313-delivery63-evidence/`.
The run used network `py313-delivery63-network` (`10.254.63.0/24`), loopback
ports 19780/19790, SQL database `py313_rebuild_delivery63`, Mongo database and
cache/search/queue namespaces `py313_delivery63`, and dedicated volumes.

| Gate | Delivery63 result | Evidence |
| --- | --- | --- |
| D0 paired source/resource isolation | PASS | `preflight.json`, `export.txt`, `commands.jsonl`, labeled resources |
| D1 full dependency installation/source identity | PASS: 315 distributions, `uv pip check`, all 20 registered source trees | `install.txt`, `installed-source-identity.txt` |
| D3 new development schema and LMS/CMS checks | PASS: local-model-sync, 149 apps, 316 models/tables, zero historical migration rows; checks pass with recorded warnings | `initialize-schema.txt`, `lms-check.txt`, `cms-check.txt` |
| D3 theme, npm, XModule, frontend, locale/static builds | PASS: both Webpack builds report 120 chunks | `stage-theme.txt`, `npm-ci.txt`, `xmodule-assets.txt`, `frontend-assets.txt`, locale/static logs |
| D3 focused Studio Logs and reindex permissions tests | PASS: one test each | `d63-studio-logs.txt`, `d63-reindex-author.txt` |
| D3 LMS/Studio sign-in | PASS | browser evidence and `d63-cms-http-log.txt` |
| D3 Elasticsearch and product search | **FAIL infrastructure**: Elasticsearch exited 137 with `OOMKilled=true`; CMS `/course_search/` returned 500 because `elasticsearch` no longer resolved | `delivery63-elasticsearch-oom.txt`, `delivery63-cms-http-log.txt` |
| D3 Studio create/edit/publish; learner, draft, permission/org, worker/search, storage, SCORM/ILT, restart | NOT RUN to completion | no course was created; Studio Create remained disabled while the course search UI failed; repeat on a fresh run |
| D4 independent checkout rebuild | NOT RUN | requires a passing final pair |
| D5 local delivery candidate | NOT RUN | no push or PR |

The Elasticsearch container had no cgroup memory cap and used a 256 MiB JVM
heap. At the post-failure diagnostic snapshot, Docker Desktop's 8 GiB VM showed
about 838 MiB `MemAvailable` and less than 1 MiB free swap. No older delivery
container, volume, network or database was stopped or changed. Delivery63 is
failure history and must not be restarted, patched or reused for acceptance.

## Previous replay: delivery62 (focused test fixes; browser authoring incomplete)

Delivery62 used platform `aed8961d6920954068949afbcf34440ee94bd4cd`, devstack
`66d1795f69677907baa441739ae4553b643ee511`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, and the same Docker Desktop runtime
image ID. It used network `py313-delivery62-network` (`10.254.62.0/24`), ports
19680/19690, SQL `py313_rebuild_delivery62`, run-scoped namespaces and dedicated
volumes. Canonical config SHA256 `fdd39103edab50348f7358e91fe3aade9138ebafc2d0c2fab1aa10899b2443c0`;
evidence `/Users/noahwang/workspace/hawthorn/py313-delivery62-evidence/`.

D0/D1, fresh local-model-sync schema, LMS/CMS settings checks and resource
build passed. The focused course-author reindex test passed 1/1. A new Studio
Logs rendering regression test first failed with `NameError: Undefined`; the
failure is retained in `d62-studio-logs-template-test01.txt`. Platform
`36d1a28ec7dfe85c6036fd52bd82c926fc2492ec` replaces the Python 2 `unicode(...)`
template call and adds a real Mako rendering test; rerun `d62` test
`d62-studio-logs-template-test02.txt` passed 1/1, and the test passed again in
delivery63. The D62 browser request to `/studiologs/<course>` still returned
500 before that fix. Studio's course-create attempt did not enable Create, so
no authoring or learner/business acceptance is claimed. Delivery62 resources
remain separate and are not reused for candidate acceptance.

## Previous replay: delivery61 (runtime gates pass; test selection/import failed)

Delivery61 inputs: platform `8f31fa2d9eaa4e1deeb2762b143b536a338d9f02`, devstack
`4f085f413ff60d407680ed527f9f27f3d2011aa3`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, Docker Desktop runtime image ID
`sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c`.
Native linux/arm64, Python 3.13.14, Django 5.2.13. Canonical config hash
`b5b5904449d403f61878d0bccc035a98916bb58cd4296b84b7bb561a311b6faa`; evidence
`/Users/noahwang/workspace/hawthorn/py313-delivery61-evidence/`. New resources
are isolated to network `10.254.61.0/24`, ports 19580/19590, database and
cache/search/queue namespace `delivery61`, with dedicated volumes.

D0 export/resources, D1 full installation (315 packages, `uv pip check`, 20
source identities), D3 local-model-sync schema, LMS/CMS checks, and full assets
all passed. The targeted CMS test action ran but test collection failed before
its assertion because the selected legacy `test_course_index.py` module imports
`factory_boy`, which is intentionally absent from the full runtime dependency
lock. Evidence: `cms-course-reindex-auth01.txt` and `commands.jsonl`. This is a
test-selection/dependency limitation, not an installation or product failure.

Platform commit `aed8961d6920954068949afbcf34440ee94bd4cd` adds a smaller focused
endpoint test without factory fixtures; delivery62 passed it. Delivery61 remains
incomplete and its containers/data are not reused for acceptance.

Browser LMS/CMS sign-in, real Studio course create/edit/publish, learner content,
permission/organization matrix, real search/worker result, storage, SCORM, ILT,
restart persistence and D4 remain open on the final pair.

## Previous replay: delivery60 (host test-dispatch failure; replay not candidate)

Delivery60 used platform `8f31fa2d9eaa4e1deeb2762b143b536a338d9f02`, devstack
`8f5f6e97d27126c26eb6e56e0a9b684d785609a4`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, runtime image ID
`sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c`.
It used new network `10.254.60.0/24`, loopback ports 19480/19490, a new SQL
DB/Mongo DB, dedicated volumes and `delivery60` cache/search/queue namespaces.
Canonical configuration hash is `f979f31e08459fdb2a23ac79918a1c0f11667740147b180eb0e02131d1c75ce9`;
evidence is `/Users/noahwang/workspace/hawthorn/py313-delivery60-evidence/`.

D0, D1, fresh schema/LMS/CMS checks and D3 assets passed exactly as recorded in
`preflight.json`, `install.txt`, `installed-source-identity.txt`,
`initialize-schema.txt`, `frontend-assets.txt` and the locale/static logs.
The targeted CMS regression test was then requested with the new recorded test
entry, but the host replay runner raised `UnboundLocalError` before `capture()`
and before any `docker exec` or test database operation. The failure is recorded
in `delivery60-test-action-failure.txt` and `commands.jsonl`. This is a harness
FAIL, not a product test result. The dispatcher fix is in devstack commit
`47efd68399fceaf8e99d2cf577b7e5b47a6e80a9` and its 28 local runner tests pass.
Delivery60 is retained as incomplete and its containers/resources are not reused
or modified for acceptance.

## Latest replay: delivery59 (business authorization failed; repair replay pending)

Inputs: platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack
`88cdf21e1423d0ae91f9776dd456722d1710de1b`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, runtime image ID
`sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c`.
Native linux/arm64, Python 3.13.14, Django 5.2.13. Config raw SHA256 and
canonical configuration SHA256 are recorded in the private run config and
`commands.jsonl`; evidence root is
`/Users/noahwang/workspace/hawthorn/py313-delivery59-replay-evidence/`.
Resources use Docker Desktop network `10.254.59.0/24`, loopback ports
19380/19390, dedicated runtime/service volumes, SQL database
`py313_rebuild_delivery59`, Mongo database `py313_delivery59` and matching
cache/search/queue namespaces. No delivery58 or older data was imported.

D0 preflight, export and resource creation passed. D1 installed all 315 locked
distributions in a new venv, `uv pip check` passed, and all 20 registered source
trees matched installed bytes. D3 local-model-sync initialized a fresh
development schema (149 apps, 316 models/tables, zero historical migration
rows); LMS/CMS checks passed with recorded warnings. npm/XModule, both
120-chunk Webpack builds, locale/static collection and HTTP/worker startup
passed. Browser sign-in, Studio course create/edit and ordinary learner
enrollment passed.

**FAIL:** the Studio publish modal called
`GET /course/course-v1:PY313+Delivery_delivery59+2026/search_reindex`, which
returned 403 on release and retry. Logs and captured course state are retained
under the evidence root. The handler applied a platform-role allowlist before
calling `reindex_course_and_check_access`, which already checks target-course
author access. The named author had the course instructor role without Django
staff/superuser privilege. The course was marked released in modulestore, but
the publishing UI did not reach its success state. This run cannot validate the
fix or downstream published learner/search scenarios.

Platform commit `8f31fa2d9eaa4e1deeb2762b143b536a338d9f02` removes the redundant
platform-role gate and adds a regression test for own-course instructor access
and denial on an unrelated course. Devstack commit `17ab66a5e15db0571dc0f8d0221bf5ea9f050c34`
adds an explicit, recorded targeted Django test action using the replay's
platform root. Delivery61 passed runtime gates but its legacy test module could not import the test-only `factory_boy` package. The next full replay is delivery62 with the focused test and exact clean paired commits; use new containers, volumes, DB, ports, network and namespaces.
Do not patch or restart delivery59.

Learner-visible publication and draft isolation, complete role/organization
matrix, real search result, GridFS/File CRUD, SCORM, ILT and restart persistence
remain open on the final paired input.

## Historical replay: delivery58 (infrastructure failed)

Delivery58 is the active clean replay for the search-filter and subnet runner fixes. Inputs are platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack `77d6e8774017cbd70f8bbc8e8cd226d5fd5e2f59`, and theme `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`. Target is native linux/arm64, Python 3.13.14 and Django 5.2; runtime image is `sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`. Config file SHA256 is `ff0b08bd40bd26afbf7c2b1405290d0655c141e3d4ef1d9e9cd2313841edfcf5`; runner canonical ownership hash is `f454e0251a88d9e031b7dbf5352dc9ef3f0b747d368eecdd901e2fa0504bbdf9`. Resources use subnet `10.254.58.0/24`, loopback ports 19280/19290, SQL `py313_rebuild_delivery58`, and delivery58-only Mongo/cache/search/queue namespaces.

D0 preflight, source export and resource creation passed. The new network, six infrastructure containers, runtime container and dedicated volumes are labeled to this exact replay. D1 installed all 315 locked distributions with `uv pip sync`, passed `uv pip check`, and verified all 20 registered source trees against installed bytes. D3 local-model-sync schema initialization, natural-key sites, acceptance users, completion tracking, themes, and LMS/CMS settings checks passed; this is new-development schema creation and records zero historical migration rows. Checks retain observed warnings. D3 npm/XModule/frontend build, LMS/CMS Webpack (120 chunks each), locale generation and static collection passed.

Delivery58 then hit host VM memory exhaustion: Elasticsearch exited 137/OOMKilled after startup, and MySQL also exited 137/OOMKilled. One read-only-start retry of delivery58 Elasticsearch also OOMKilled; the new MySQL service was started once after its OOM for diagnosis. Browser login submission failed because LMS could not resolve `mysql` while MySQL was down, so this is an infrastructure FAIL rather than an authentication conclusion. No course or learning-state business assertion ran in delivery58. The OOMs, failed login request and memory readings are preserved in `delivery58-service-oom.txt`; do not treat delivery56 results as coverage for this replay.

The OrbStack VM had 16 GiB configured and about 590 MiB available with swap nearly full. Older runs were left untouched. The independent Docker Desktop daemon has an 8 GiB VM and also contains unrelated project resources that remain untouched. The delivery59 runtime image was copied read-only from OrbStack; Docker save/load preserved all 15 rootfs layer digests and parsed image config, while Desktop assigned a different local image ID (`sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c` versus OrbStack `sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`). Delivery59 used that ID and independent resource state.

Evidence root: `/Users/noahwang/workspace/hawthorn/py313-delivery58-evidence/`; private runtime inputs: `/Users/noahwang/workspace/hawthorn/py313-delivery58-private/`. The runner's `configuration_sha256` is a canonical JSON hash and differs from the raw config file SHA; both are recorded above to avoid ambiguity.

## Historical evidence baseline: delivery56

Delivery56 is a clean replay of the committed Webpack memory fix. Runtime inputs are platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack `bb22dee9eb4108291f341acfd576b72152f241eb`, and theme `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`. Runtime image is `sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`; target is native linux/arm64, Python 3.13.14, Django 5.2. Config SHA256: `3b0ccb3301ea3456a62eedbcb56303e3ff770928d7c4603c16454c6cde06f4d4`.

D0 isolated preflight/export and resource creation passed. Delivery56 uses only its new containers/volumes/network, SQL database `py313_rebuild_delivery56`, run-scoped Mongo/cache/search/queue namespace, and loopback ports 19080/19090. Test identities and service secrets were separately created with mode 600. D1 installed all 315 locked distributions without dependency bypasses; `uv pip check` and all 20 registered source byte comparisons passed. D3 new `local-model-sync` initialized 149 apps, 316 models including M2M, 316 tables, and zero historical migration rows. Both settings checks passed with recorded warnings.

The complete D3 resource build passed: npm install, XModule staging, bounded LMS/CMS Webpack (120 chunks each, both login bundles present), theme, locale generation, and static collection. Browser LMS/Studio login and course create/edit/publish were exercised. The enrolled learner opened published content and reached 100% course progress. The learner navigation exposed the title of an unpublished draft section while withholding its body, so complete draft isolation is not passed. GridFS CRUD and PyFS text/bytes/expiration passed.

Search remains failed in delivery56. The real worker completed the product indexing task and Elasticsearch contains the course plus five courseware documents, but LMS and CMS search endpoints returned zero results. The LMS content-search filter was traced to `exclude="archived"` being interpreted as a required content field, absent from courseware documents. A direct Elasticsearch comparison returned one result without that marker and zero with it. The fix, regression test, and registered source hashes were committed as devstack `9689a4104af52b003346c80b025a75f2a1678e50`; delivery56 remains immutable evidence and cannot validate the fix.

The first clean-resource attempt for that new input, delivery57, passed preflight and exported all 20 registered packages, then failed during network creation because Docker Desktop's default address pool was exhausted. It created only its newly labeled empty volumes; no network, infrastructure services, or runtime container was created. Preserve this failure and those resources. The replay runner now requires an explicit non-overlapping RFC1918 `/24` for each run. Delivery58 is the new identity replaying that committed change; delivery57 remains unchanged.

SCORM is not passed: the first staff upload returned 500; diagnosis showed the probe-created XBlock existed only on the published branch while Studio queried the draft branch. Learner and cross-org upload denials did occur. Re-run through a Studio-created draft component before judging the product path. ILT business flow, restart persistence, delayed first-publication evidence, and independent checkout rebuild remain open. Studio font 404s also remain under review. D4 and D5 have not run.

| Gate | Status | Evidence / next action |
| --- | --- | --- |
| D0 paired source/resource isolation | PASS delivery56, 58, 59; FAIL delivery57 | Per-run `preflight.json`, `export.txt`, `commands.jsonl`; delivery57 failure retained |
| D1 dependency closure | PASS delivery56, 58, 59 | Per-run `install.txt`, `installed-source-identity.txt`; 315 distributions, `uv pip check`, 20 source trees |
| D2 semantic source reconciliation | IN PROGRESS | Review outcomes and unresolved differences in `SOURCES.md`; search fix commit `9689a4104af52b003346c80b025a75f2a1678e50` awaits clean replay |
| D3 schema and LMS/CMS checks | PASS delivery56 and delivery58 | delivery58 `initialize-schema.txt`, `lms-check.txt`, `cms-check.txt`; local-model-sync only |
| D3 assets and static resources | PASS delivery56 and delivery58 | delivery58 `npm-ci.txt`, `xmodule-assets.txt`, `frontend-assets.txt`, `lms-locale-static.txt`, `cms-locale-static.txt`; 120 Webpack chunks each |
| D3 browser/course/learner workflow | PARTIAL delivery56; FAIL infrastructure delivery58; FAIL publish authorization delivery59 | delivery58 `delivery58-service-oom.txt`; delivery59 `delivery59-course-state.txt`, `commands.jsonl`; fix replay on delivery60 |
| D3 GridFS and File storage | PASS delivery56; NOT RUN delivery59 | `delivery56-gridfs-crud01.txt`, `delivery56-file-storage01.txt`; must replay on final pair |
| D3 product search and organization isolation | FAIL delivery56; BLOCKED by ES OOM delivery58; BLOCKED after publish failure delivery59 | Failures and fix history retained per run; replay on delivery60 |
| D3 SCORM / ILT | FAIL / NOT RUN delivery56; BLOCKED by service OOM delivery58; NOT RUN delivery59 | Recreate a Studio draft component and retest SCORM, then ILT on delivery60 |
| D3 restart persistence | NOT RUN | Capture snapshot after final-run business state passes; restart only that replay's owned services |
| D4 portable independent checkout | NOT RUN | Requires final paired SHA and complete instructions |
| D5 local candidate | NOT RUN | No push or PR; publish authorization not requested yet |

## Replay history

Delivery55 used platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack `4af117ba9d678ce077d3e38a855d136dd587e97f`, and theme `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`. D0/D1/schema/LMS/CMS checks passed. `npm ci` and XModule staging passed, but the full frontend command failed with exit 137 when Webpack source-map generation was OOM-killed. The failure remains in `delivery55-evidence/frontend-assets.txt`; 3 GiB, 1.5 GiB, and 512 MiB diagnostics remain recorded. A separate Webpack-only diagnostic was not treated as a full asset pass.

Devstack commit `0f4822593812682d435d9e25d1be7a604b17ceb3` caps Node at 2 GiB and disables development source maps while checking both Webpack stats/login bundles. Delivery56 is the clean replay of that fix. Native compiler memory was bounded separately in commit `4af117ba9d678ce077d3e38a855d136dd587e97f`.

Delivery54 D1 failed during lxml compilation when `cc1` was OOM-killed; no later gate ran. Evidence: `/Users/noahwang/workspace/hawthorn/py313-delivery54-evidence/install.txt`, config SHA `367cd16cf8ebb1c635a53efb208adbdb57dca9787bad6b7bb2cee921a7107142`.

Delivery53 had a full install, schema/check/assets pass, Studio authoring, learner completion, and real GridFS CRUD. Learner course home returned HTTP 500; platform fix `7962745ac4d0966442498326b1dad25696ea4c6f` passes the request context and is included in delivery56. Search, delayed publish/draft, full permission matrix, SCORM/ILT, and restart persistence did not pass there.

Keep all run-scoped failures beside later fixes; never overwrite an evidence label or carry a result to different runtime inputs. See [`ACCEPTANCE-MATRIX.md`](ACCEPTANCE-MATRIX.md) and [`REPLAY-HISTORY.md`](REPLAY-HISTORY.md).

## Contract and boundaries

Scope is native linux/arm64 and a fresh local development database. This is not production readiness, a historical database upgrade, real IdP, external ORA2, full-repository test, capacity, or amd64 evidence. Frozen platform refs remain master `5c2015893ef357436a36e7590646efb9ab1bb804`, py313-master `fbb305460bcc9d8ebcb440824de3d976d65063c3`, and py313-wip `4759a01524b497522910b9035b16c852e70d053f`. No push or PR has occurred. The current delivery branches are local working copies and must be checked against fresh remote SHA before D5.
