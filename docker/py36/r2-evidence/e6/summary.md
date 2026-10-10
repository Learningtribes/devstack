# E6 browser gates, group 1 (dashboard; enrollment and course view)

Date: 2026-10-10 (UTC 02:20-03:10). Source `platform-r2-py36-src@0ac3bfa6d09`
(PR #2401 head, clean). Runtimes: Python 3.6 `ltdps/edxapp:py36-r2-20261009`
= `sha256:8c2e7df2e03d`; Python 2.7 control
`ltdps/edxapp:py36-r2-py27-runner-20261009` = `sha256:e5ecccf98eb9`.
Harness `platform-browser-acceptance-harness@68255fc7742` (lib/tests clean,
copied per run), Playwright `1.61.1` image
`mcr.microsoft.com/playwright@sha256:5b8f294aff90…`.

## Result

Status: **functional parity proven; strict pass criterion not met** (plan
§E6: zero console, page, request, 4xx/5xx diagnostics on both runtimes).

- Final runs (`final-py36/`, `final-py27/`, harness default 30 s budget):
  30 surfaces each, **26 passed / 4 failed on both, identical outcome per
  surface** (`results.json`). Wall time Python 3.6 54.8 s, Python 2.7 1.2 min.
- Rendered HTML of the 8 R2-changed surfaces (dashboard, course home,
  courseware section, progress, about, Studio home, outline, course team) is
  identical between runtimes up to dict/JSON key order and random tokens
  (`diagnosis/html-parity.txt`: non-alphanumeric character diff = 0 on all 8).
- The only runtime-specific diagnostic is Python 3.6 `GET
  /enrolled_ilt_sessions` → 500 (`final-py36/service-log-errors.txt`; Python
  2.7 log has no 5xx).

## The 4 failures (same on both runtimes)

| Surface | Class | Cause |
|---|---|---|
| pr-2396 "course_modes chooser still routed (KEEP)" → 404 | Checklist composition conflict | #2395 (also in R2) removes the chooser route; the #2396 checklist was written against a base without #2395. 404 is the R2-correct result (pr-2395 "chooser route removed" passes) |
| p1b-dashboard "QA last activity item renders" | Fixture mismatch | R1's p1b fixture used a freshly created, empty QA course, so `get_last_accessed_courseware` fell back to course home. The shared QA course has chapters and stored positions, so both runtimes link to `courseware/qa_chapter2/qa_seq/` (`diagnosis/dashboard-last-activity.txt`). R2's template change (fallback moved into the helper) is correct |
| p1b-dashboard "click reaches QA course home" | Fixture mismatch | Same cause; the R2 checklist below asserts the courseware target and passes the click navigation |
| r2-py3-templates "click reaches courseware section" | Diagnostics (strict) | Navigation and target 200 pass on both. Diagnostics: both runtimes `IltGlobals.js` 404 + `FeedbackForm is not defined` (asset volume, see below); Python 3.6 additionally `/enrolled_ilt_sessions` 500 (XBlock inventory, see below) |

## Findings

1. **Python 3.6 image XBlock inventory gap (owner decision).** `ilt-xblock`
   and `xblock-pdf` are not installed in the Python 3.6 image; `xblock.v1`
   has 45 entry points vs 95 on the Python 2.7 devstack (50 missing incl.
   `ilt`, `pdf`, `discussion`, `problem-builder`, `done`, `rate`, `iframe`,
   `edx_sga`). Inherited from the R1 lock (`py36-git-requirements.txt`).
   `get_enrolled_ilt` returns 500 `ILT is disabled` on `ImportError`, so the
   dashboard ILT calendar request fails on Python 3.6. `xblock-pdf` is
   declared in Platform `base.txt`; `ilt-xblock` is declared nowhere in
   Platform requirements (devstack installs `/edx/src/xblock-ilt`).
   Not an R2 diff defect (`diagnosis/xblock-inventory-gap.txt`).
2. **Stale shared asset volume (environment).** `devstack_edxapp_lms_assets`
   `webpack-stats.json` (2026-10-09) names `IltGlobals`, but `bundles/`
   (2026-08-14) predates the entry (`414fd9a64f0`, 2026-09-21), so
   `<%static:webpack entry="IltGlobals"/>` 404s on both runtimes. Plan §E6
   requires staging R2-preview assets before judging; not done yet
   (`diagnosis/asset-volume.txt`).
3. **Docker DNS 5 s stall (harness, fixed).** Python 3.6 runs took 5 min
   vs 1.2 min. py-spy showed request threads blocked in `MySQLdb.connect`;
   the Python 3.6 client (mysqlclient 1.4.6) resolves with parallel A/AAAA
   lookups, and Docker's embedded DNS intermittently loses one reply (glibc
   waits the 5 s timeout). `RES_OPTIONS=single-request` on the E6 service
   containers: 0 stalls in 1,500 lookups / 300 connects; suite 5 min → 55 s
   (`diagnosis/dns-stall.txt`). Environment-only; production does not use
   Docker's resolver.

## Isolation

Each runtime has a private `mysql:5.6` (tmpfs) loaded from one read-only
`mysqldump --single-transaction` of shared `edxapp` + `edxapp_csmh`, plus a
private memcached; Mongo and Elasticsearch are shared read-only. Shared
MySQL is unchanged after all runs (qacert/qastaff `last_login`
2026-09-28, localhost:18000 `course_org_filter` `edX`, 66 Site
configuration history rows, 501 sessions, 5 BlockCompletion rows); both
private clones show the writes (new logins, filter `QA`, history 67,
BlockCompletion 6) (`isolation/`).

## Fixture (private clone only)

`r2-e6-fixture.py`, run by `run-r2-e6-services.sh start` before the servers
start: asserts every `DATABASES` alias points at the private MySQL, keeps
qacert's existing BlockCompletion, and sets localhost:18000
`course_org_filter` to `QA` (the fork's dashboard compares one org string;
R1's p1b fixture used the same value). Output in `final-*/fixture.txt`.

## Harness

- `run-r2-e6-services.sh clone | {py36|py27} {start|status|cleanup|logs}`:
  LMS owns the network namespace and publishes 18300/18310 (Python 3.6) or
  18400/18410 (Python 2.7); CMS and the Playwright container join it, so
  `localhost:18000/18010` are the runtime under test. Celery eager, memory
  broker, discussion service off (shared forum), as R1.
- `r2-e6-browser.sh {py36|py27} <out> <checklist>...`: copies harness code
  and checklists per run and records sha256s; `E6_TEST_TIMEOUT_MS` (default
  30000; the final runs used the default).
- `e6-checklists/r2-py3-templates.yml`: R2-specific surfaces for the
  Py3-converted Mako templates on real QA data.
- `history/`: earlier runs (run1-run4 Python 3.6 before the fixture/DNS fixes,
  run1 Python 2.7 at a 90 s budget), outcome-identical where compared.
