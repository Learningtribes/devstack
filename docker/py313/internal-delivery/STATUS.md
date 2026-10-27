# Python 3.13 internal delivery status

Updated: 2026-10-28 (Asia/Shanghai). Goal remains active. State: **local delivery candidate incomplete**.

## Current evidence baseline: delivery56

Delivery56 is a clean replay of the committed Webpack memory fix. Runtime inputs are platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack `bb22dee9eb4108291f341acfd576b72152f241eb`, and theme `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`. Runtime image is `sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`; target is native linux/arm64, Python 3.13.14, Django 5.2. Config SHA256: `3b0ccb3301ea3456a62eedbcb56303e3ff770928d7c4603c16454c6cde06f4d4`.

D0 isolated preflight/export and resource creation passed. Delivery56 uses only its new containers/volumes/network, SQL database `py313_rebuild_delivery56`, run-scoped Mongo/cache/search/queue namespace, and loopback ports 19080/19090. Test identities and service secrets were separately created with mode 600. D1 installed all 315 locked distributions without dependency bypasses; `uv pip check` and all 20 registered source byte comparisons passed. D3 new `local-model-sync` initialized 149 apps, 316 models including M2M, 316 tables, and zero historical migration rows. Both settings checks passed with recorded warnings.

The complete D3 resource build passed: npm install, XModule staging, bounded LMS/CMS Webpack (120 chunks each, both login bundles present), theme, locale generation, and static collection. Browser LMS/Studio login and course create/edit/publish were exercised. The enrolled learner opened published content and reached 100% course progress. The learner navigation exposed the title of an unpublished draft section while withholding its body, so complete draft isolation is not passed. GridFS CRUD and PyFS text/bytes/expiration passed.

Search remains failed in delivery56. The real worker completed the product indexing task and Elasticsearch contains the course plus five courseware documents, but LMS and CMS search endpoints returned zero results. The LMS content-search filter was traced to `exclude="archived"` being interpreted as a required content field, absent from courseware documents. A direct Elasticsearch comparison returned one result without that marker and zero with it. The fix, regression test, and registered source hashes were committed as devstack `9689a4104af52b003346c80b025a75f2a1678e50`; delivery56 remains immutable evidence and cannot validate the fix.

The first clean-resource attempt for that new input, delivery57, passed preflight and exported all 20 registered packages, then failed during network creation because Docker Desktop's default address pool was exhausted. It created only its newly labeled empty volumes; no network, infrastructure services, or runtime container was created. Preserve this failure and those resources. The replay runner now requires an explicit non-overlapping RFC1918 `/24` for each run. After committing and validating that change, use a new delivery58 identity with its own subnet, credentials, and resources.

SCORM is not passed: the first staff upload returned 500; diagnosis showed the probe-created XBlock existed only on the published branch while Studio queried the draft branch. Learner and cross-org upload denials did occur. Re-run through a Studio-created draft component before judging the product path. ILT business flow, restart persistence, delayed first-publication evidence, and independent checkout rebuild remain open. Studio font 404s also remain under review. D4 and D5 have not run.

| Gate | Status | Evidence / next action |
| --- | --- | --- |
| D0 paired source/resource isolation | PASS delivery56; FAIL delivery57 | delivery56 evidence above; delivery57 `preflight.json`, `export.txt`, `commands.jsonl`, `create-network.txt`; next fresh attempt is delivery58 with explicit subnet |
| D1 dependency closure | PASS delivery56 | `install.txt`, `installed-source-identity.txt`; 315 distributions, `uv pip check`, 20 source trees |
| D2 semantic source reconciliation | IN PROGRESS | Review outcomes and unresolved differences in `SOURCES.md`; search fix commit `9689a4104af52b003346c80b025a75f2a1678e50` awaits clean replay |
| D3 schema and LMS/CMS checks | PASS delivery56 | `initialize-schema.txt`, `lms-check.txt`, `cms-check.txt`; local-model-sync only |
| D3 assets and static resources | PASS delivery56 | `npm-ci.txt`, `xmodule-assets.txt`, `frontend-assets.txt`, `webpack-stats-audit.txt`, `lms-locale-static.txt`, `cms-locale-static.txt` |
| D3 browser/course/learner workflow | PARTIAL delivery56 | Manual LMS/Studio browser flow; `completion-tracking.txt`; learner draft title still visible |
| D3 GridFS and File storage | PASS delivery56 | `delivery56-gridfs-crud01.txt`, `delivery56-file-storage01.txt` |
| D3 product search and organization isolation | FAIL delivery56 | `delivery56-product-search-worker01.txt`, `delivery56-courseware-search-lms01.txt`; source fix pending delivery57 |
| D3 SCORM / ILT | FAIL / NOT RUN delivery56 | `delivery56-scorm-routed01.txt`, `delivery56-scorm-branch-audit01.txt`; correct draft-branch component, then retest; ILT still required |
| D3 restart persistence | NOT RUN | Capture snapshot, restart only delivery57-owned runtime services, verify course/assets/progress |
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
