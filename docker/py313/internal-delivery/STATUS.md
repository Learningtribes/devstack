# Python 3.13 internal delivery status

Updated: 2026-10-28 (Asia/Shanghai). Goal remains active. State: **local delivery candidate incomplete**.

## Current replay: delivery56

Delivery56 is a complete fresh replay of the committed Webpack memory fix. Exact runtime inputs are platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack `bb22dee9eb4108291f341acfd576b72152f241eb`, and theme `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`. Runtime image is `sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`; target is native linux/arm64, Python 3.13.14, Django 5.2. Config SHA256: `3b0ccb3301ea3456a62eedbcb56303e3ff770928d7c4603c16454c6cde06f4d4`.

D0 isolated preflight/export and resource creation passed. It uses new containers/volumes/network, SQL database `py313_rebuild_delivery56`, run-scoped Mongo/cache/search/queue namespace, and loopback ports 19080/19090. Service secrets and test identities were generated separately with mode 600. The frozen export contains only the committed paired Git content.

D1 full installation passed: all 315 locked distributions installed without dependency bypasses, `uv pip check` passed, and all 20 registered source trees matched their installed bytes. D3 fresh `local-model-sync` initialized 149 apps, 316 models including M2M, 316 tables and zero historical migration rows. Site/theme/user setup and both LMS/CMS checks passed; warnings remain in the evidence. The full assets phase (`npm ci`, XModule, bounded Webpack, theme, locale/static) is currently running; do not claim its outcome until all commands exit and stats are checked.

| Gate | Current status | Evidence |
| --- | --- | --- |
| D0 source/resource isolation | PASS delivery56 | `delivery56-evidence/preflight.json`, `export.txt`, `commands.jsonl`; config SHA above |
| D1 dependency closure | PASS delivery56 | `install.txt`, `installed-source-identity.txt`; 315 distributions and 20 sources |
| D2 semantic source reconciliation | IN PROGRESS | Final behavior and security review remains open |
| D3 new schema and LMS/CMS checks | PASS delivery56 | `initialize-schema.txt`, setup logs, `lms-check.txt`, `cms-check.txt` |
| D3 full asset build | RUNNING delivery56 | `npm-ci.txt`, `xmodule-assets.txt`, `frontend-assets.txt`, locale/static outputs pending |
| D3 services/browser/business/permissions/storage/search/worker/restart | NOT RUN delivery56 | Run only after assets complete |
| D4 portable independent checkout | NOT RUN | Requires final paired input and portable instructions |
| D5 local candidate | NOT RUN | No push/PR has been performed or authorized |

## Replay history

Delivery55 used platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack `4af117ba9d678ce077d3e38a855d136dd587e97f`, and theme `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`. D0/D1/schema/LMS/CMS checks passed. `npm ci` and XModule asset staging passed, but the complete frontend phase failed with exit 137 when Webpack source-map generation was OOM-killed. The failure remains in `delivery55-evidence/frontend-assets.txt`; the 3 GiB, 1.5 GiB, and 512 MiB diagnostics are also retained. A separate Webpack-only diagnostic succeeded with a 2 GiB heap and `--no-devtool`, and verified 120 chunks for both systems; it was not treated as a complete asset pass.

The Webpack fix is devstack commit `0f4822593812682d435d9e25d1be7a604b17ceb3`: `build_frontend.sh` caps Node at 2 GiB and omits development-only source maps, while checking both webpack stats/login bundles. Delivery56 is the clean replay of that committed behavior. Native compiler memory was bounded separately in devstack commit `4af117ba9d678ce077d3e38a855d136dd587e97f`.

Delivery54 D1 failed during lxml compilation when `cc1` was killed by OOM; no later gate ran. Evidence: `/Users/noahwang/workspace/hawthorn/py313-delivery54-evidence/install.txt`, config SHA `367cd16cf8ebb1c635a53efb208adbdb57dca9787bad6b7bb2cee921a7107142`.

Delivery53 had a full install, schema/check/assets pass, Studio authoring, learner completion, and real GridFS CRUD. Learner course home returned HTTP 500; platform fix `7962745ac4d0966442498326b1dad25696ea4c6f` passes the request context and is included in delivery56. Delayed publish/draft, full permission matrix, published-course search, SCORM/ILT, and restart persistence remained open in delivery53.

See [`ACCEPTANCE-MATRIX.md`](ACCEPTANCE-MATRIX.md) for per-scenario results and [`REPLAY-HISTORY.md`](REPLAY-HISTORY.md) for older diagnostic snapshots. Failures remain preserved by run and output label.

## Contract and boundaries

Scope is native linux/arm64 and a fresh local development database. This is not production readiness, a historical database upgrade, real IdP, external ORA2, full-repository test, capacity, or amd64 evidence. Frozen platform refs remain master `5c2015893ef357436a36e7590646efb9ab1bb804`, py313-master `fbb305460bcc9d8ebcb440824de3d976d65063c3`, and py313-wip `4759a01524b497522910b9035b16c852e70d053f`. Nothing has been pushed; remote delivery branches remain behind the local candidate.
