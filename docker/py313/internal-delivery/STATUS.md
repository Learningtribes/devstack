# Python 3.13 internal delivery status

Updated: 2026-10-28 (Asia/Shanghai). Goal remains active. State: **local delivery candidate incomplete**.

## Latest replay: delivery58 (infrastructure failed)

Delivery58 is the active clean replay for the search-filter and subnet runner fixes. Inputs are platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack `77d6e8774017cbd70f8bbc8e8cd226d5fd5e2f59`, and theme `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`. Target is native linux/arm64, Python 3.13.14 and Django 5.2; runtime image is `sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`. Config file SHA256 is `ff0b08bd40bd26afbf7c2b1405290d0655c141e3d4ef1d9e9cd2313841edfcf5`; runner canonical ownership hash is `f454e0251a88d9e031b7dbf5352dc9ef3f0b747d368eecdd901e2fa0504bbdf9`. Resources use subnet `10.254.58.0/24`, loopback ports 19280/19290, SQL `py313_rebuild_delivery58`, and delivery58-only Mongo/cache/search/queue namespaces.

D0 preflight, source export and resource creation passed. The new network, six infrastructure containers, runtime container and dedicated volumes are labeled to this exact replay. D1 installed all 315 locked distributions with `uv pip sync`, passed `uv pip check`, and verified all 20 registered source trees against installed bytes. D3 local-model-sync schema initialization, natural-key sites, acceptance users, completion tracking, themes, and LMS/CMS settings checks passed; this is new-development schema creation and records zero historical migration rows. Checks retain observed warnings. D3 npm/XModule/frontend build, LMS/CMS Webpack (120 chunks each), locale generation and static collection passed.

Delivery58 then hit host VM memory exhaustion: Elasticsearch exited 137/OOMKilled after startup, and MySQL also exited 137/OOMKilled. One read-only-start retry of delivery58 Elasticsearch also OOMKilled; the new MySQL service was started once after its OOM for diagnosis. Browser login submission failed because LMS could not resolve `mysql` while MySQL was down, so this is an infrastructure FAIL rather than an authentication conclusion. No course or learning-state business assertion ran in delivery58. The OOMs, failed login request and memory readings are preserved in `delivery58-service-oom.txt`; do not treat delivery56 results as coverage for this replay.

The OrbStack VM had 16 GiB configured and about 590 MiB available with swap nearly full. Older runs were left untouched. An independent Docker Desktop daemon is available with an 8 GiB VM; it contains unrelated project resources that remain untouched. Replay `delivery59` will use that context, unique resources and the same runtime image contents. Docker save/load preserved all 15 rootfs layer digests and parsed image config, while Desktop assigned a different local image ID (`sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c` versus OrbStack `sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`); the Desktop ID will be pinned in the new run config. This engine change does not inherit any delivery58 data or service state.

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
| D0 paired source/resource isolation | PASS delivery56 and delivery58; FAIL delivery57 | delivery58 `preflight.json`, `export.txt`, `create-network.txt`, `create-infra.txt`, `create-runtime.txt`; delivery57 failure retained |
| D1 dependency closure | PASS delivery56 and delivery58 | delivery58 `install.txt`, `installed-source-identity.txt`; 315 distributions, `uv pip check`, 20 source trees |
| D2 semantic source reconciliation | IN PROGRESS | Review outcomes and unresolved differences in `SOURCES.md`; search fix commit `9689a4104af52b003346c80b025a75f2a1678e50` awaits clean replay |
| D3 schema and LMS/CMS checks | PASS delivery56 and delivery58 | delivery58 `initialize-schema.txt`, `lms-check.txt`, `cms-check.txt`; local-model-sync only |
| D3 assets and static resources | PASS delivery56 and delivery58 | delivery58 `npm-ci.txt`, `xmodule-assets.txt`, `frontend-assets.txt`, `lms-locale-static.txt`, `cms-locale-static.txt`; 120 Webpack chunks each |
| D3 browser/course/learner workflow | PARTIAL delivery56; FAIL infrastructure delivery58 | delivery58 login form rendered, submit failed while new MySQL was OOM-down; `delivery58-service-oom.txt`; no course flow was run |
| D3 GridFS and File storage | PASS delivery56 | `delivery56-gridfs-crud01.txt`, `delivery56-file-storage01.txt` |
| D3 product search and organization isolation | FAIL delivery56; BLOCKED by ES OOM delivery58 | delivery56 failure/fix history retained; delivery58 `delivery58-service-oom.txt`; replay on delivery59 |
| D3 SCORM / ILT | FAIL / NOT RUN delivery56; BLOCKED by service OOM delivery58 | delivery56 SCORM branch failure retained; delivery59 must create a Studio draft component and retest SCORM, then ILT |
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
