# Python 3.13 internal delivery status

Updated: 2026-10-28 (Asia/Shanghai). Goal remains active. State: **local delivery candidate incomplete**.

## Latest replay: delivery55 (failed at frontend build)

Delivery55 used platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack `4af117ba9d678ce077d3e38a855d136dd587e97f`, and theme `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`. Config SHA256 is `22a79e2f77013309e0aafe858eb0eda67270df8e66c65e8bfa77d4a85cf1ddea`; target was native linux/arm64, Python 3.13.14, Django 5.2.

D0 isolated preflight, committed export, fresh service/runtime containers, and frozen input checks passed. The new SQL/Mongo/cache/search/queue namespaces were run-scoped to delivery55, with loopback ports 18980/18990. Credentials and service secrets were separately generated with mode 600.

D1 full install passed: `uv pip sync` installed all 315 locked distributions without dependency bypasses; `uv pip check` passed; all 20 registered source trees matched their installed bytes. lxml 5.3.2 and xmlsec 1.3.17 compiled from source and linked to the image's system libxml2 2.9.14. Installer source is devstack commit `4af117ba9d678ce077d3e38a855d136dd587e97f`, which caps compiler optimization for the build subprocess. Evidence: `delivery55-evidence/install.txt`, `installed-source-identity.txt`, `native-build-outcome.txt`, and `lxml-xmlsec-native-linkage.txt`.

D3 fresh local-model-sync initialized 149 apps, 316 models including M2M, 316 tables, and zero historical migration rows. Site/theme/acceptance-user setup and both LMS/CMS checks passed; warnings are retained in their logs. `npm ci` and XModule asset staging passed. The full `build_frontend.sh` then failed with exit 137 when the Docker VM OOM killer terminated Webpack while generating development source maps. Locale/static collection, service startup, browser/business checks, and restart checks did not run on delivery55.

Follow-up diagnostic labels preserve the failure and tests: 3 GiB and 1.5 GiB heap caps alone were still killed; a 512 MiB cap produced an explicit V8 heap-exhaustion failure; Webpack 4 succeeded with a 2 GiB heap cap and `--no-devtool`, then verified `status=done` and 120 chunks for each of LMS/CMS. This was a bounded diagnostic on delivery55, not a complete asset phase. The fix is committed as devstack `0f4822593812682d435d9e25d1be7a604b17ceb3`; a clean replay is required before counting it as a pass.

## Stage status

| D stage | Status | Evidence |
| --- | --- | --- |
| D0 source/resource isolation | PASS delivery55 | `delivery55-evidence/preflight.json`, `export.txt`, `commands.jsonl`; config SHA above |
| D1 dependency closure | PASS delivery55; delivery54 FAIL | delivery55 `install.txt`, `installed-source-identity.txt`; delivery54 OOM preserved in its own log |
| D2 semantic source reconciliation | IN PROGRESS | Source changes and dispositions still require final review and integration evidence |
| D3 new schema and LMS/CMS checks | PASS delivery55 | `initialize-schema.txt`, `natural-sites.txt`, `acceptance-users.txt`, `completion-tracking.txt`, `site-themes.txt`, `lms-check.txt`, `cms-check.txt` |
| D3 full asset phase | FAIL delivery55; fix committed | `npm-ci.txt` and `xmodule-assets.txt` pass; `frontend-assets.txt` exit 137. Diagnostic webpack success is not a full phase pass |
| D3 services/browser/business/security/storage/search/worker/restart | NOT RUN delivery55 | Final paired replay required |
| D4 portable independent checkout | NOT RUN | Requires final pair and portable instructions |
| D5 local candidate | NOT RUN | No push or PR has been performed or authorized |

## Previous replay results

Delivery54 used platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack `8065141303cb1fa32055554c1334b197ab831cf1`, and the same theme SHA. D0 preflight/export passed. D1 installation **failed** in 163 seconds during lxml compilation (`cc1` killed); its runtime cgroup recorded an OOM kill. Evidence remains at `/Users/noahwang/workspace/hawthorn/py313-delivery54-evidence/install.txt`, config SHA `367cd16cf8ebb1c635a53efb208adbdb57dca9787bad6b7bb2cee921a7107142`. No later gate ran on delivery54.

Delivery53 used platform `990cdc0d7df7f0a817d026a7ab4e1e23db721e54` and devstack `ac9b6af1e924e910b45bc98aca16cf03ada78403`. Full install/source identity, local schema, LMS/CMS checks, asset build, Studio create/edit/publish, learner completion, and real Mongo/GridFS CRUD passed. Learner course home returned HTTP 500; platform fix `7962745ac4d0966442498326b1dad25696ea4c6f` passes `request` to the template bundle helper and remains to be verified in the final replay. Delayed first publish/draft isolation, full role matrix, published-course search, SCORM/ILT, and restart persistence were not closed on delivery53.

Detailed older diagnostic history remains in [`REPLAY-HISTORY.md`](REPLAY-HISTORY.md). Per-scenario outcomes and commands are in [`ACCEPTANCE-MATRIX.md`](ACCEPTANCE-MATRIX.md).

## Contract and boundaries

Scope is native linux/arm64 and a fresh local development database. This is not production readiness, a historical database upgrade, real IdP, external ORA2, full-repository test, capacity, or amd64 evidence. Frozen platform refs remain master `5c2015893ef357436a36e7590646efb9ab1bb804`, py313-master `fbb305460bcc9d8ebcb440824de3d976d65063c3`, and py313-wip `4759a01524b497522910b9035b16c852e70d053f`. Nothing has been pushed; remote delivery branches remain behind the local candidate.
