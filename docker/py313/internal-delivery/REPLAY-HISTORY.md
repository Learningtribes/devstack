# Historical replay status snapshots

Archived status text from before the delivery54/55 runs. This is retained for audit history only; current state is in `STATUS.md` and `ACCEPTANCE-MATRIX.md`.

## Delivery61 — 2026-10-28

Inputs were platform `8f31fa2d9eaa4e1deeb2762b143b536a338d9f02`, devstack
`4f085f413ff60d407680ed527f9f27f3d2011aa3`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, Docker Desktop runtime image
`sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c`,
Python 3.13.14, Django 5.2.13, native linux/arm64. It used network
`py313-delivery61-network` (`10.254.61.0/24`), ports 19580/19590, a new SQL DB,
Mongo DB, service namespaces and volumes. Canonical config hash:
`b5b5904449d403f61878d0bccc035a98916bb58cd4296b84b7bb561a311b6faa`; evidence:
`/Users/noahwang/workspace/hawthorn/py313-delivery61-evidence/`.

D0, D1 installation/source identity, schema/settings and assets passed. The
selected CMS test module failed collection because `factory_boy` was absent
from the runtime lock; the test assertion never ran. This is a test harness
selection limitation, not a product result. Log and exact command remain in
`cms-course-reindex-auth01.txt` and `commands.jsonl`. Platform
`aed8961d6920954068949afbcf34440ee94bd4cd` now includes a focused
factory-independent endpoint test. Delivery62 must replay it on fresh resources.

## Delivery60 — 2026-10-28

Inputs were platform `8f31fa2d9eaa4e1deeb2762b143b536a338d9f02`, devstack
`8f5f6e97d27126c26eb6e56e0a9b684d785609a4`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, Docker Desktop runtime image
`sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c`,
Python 3.13.14, Django 5.2.13, native linux/arm64. It used new network
`py313-delivery60-network` (`10.254.60.0/24`), ports 19480/19490, new DBs,
service namespaces and volumes. Canonical config hash:
`f979f31e08459fdb2a23ac79918a1c0f11667740147b180eb0e02131d1c75ce9`; evidence:
`/Users/noahwang/workspace/hawthorn/py313-delivery60-evidence/`.

D0, full D1 install/source identity, schema/checks and assets passed. The new
CMS test dispatch action failed on the host with `UnboundLocalError` before
`capture()` and before `docker exec`, so no CMS test or test DB ran. This is a
harness failure only; no product conclusion is claimed. The failure is retained
in `delivery60-test-action-failure.txt` and `commands.jsonl`. A dispatcher fix
and 28 local runner contract tests are in devstack `47efd68399fceaf8e99d2cf577b7e5b47a6e80a9`.
Delivery61 must be a clean replay using that exact current devstack input.

## Delivery59 — 2026-10-28

Inputs were platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack
`88cdf21e1423d0ae91f9776dd456722d1710de1b`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, Docker Desktop runtime image
`sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c`,
Python 3.13.14, Django 5.2.13, native linux/arm64. It used network
`py313-delivery59-network` (`10.254.59.0/24`), ports 19380/19390, a new SQL DB,
Mongo DB, cache/search/queue namespaces, and dedicated volumes. The private
config canonical hash is `27e3812bd2e48c1c2ab5c4a3e3d466972ffa08c6a4cd8e6c64b4f79e4c48b3e2`;
commands and full config are in the private evidence root
`/Users/noahwang/workspace/hawthorn/py313-delivery59-replay-evidence/`.

D0, full D1 install/source identity, new schema, LMS/CMS checks and the complete
asset build passed. Browser sign-in, course create/edit and learner enrollment
passed. Studio's publishing modal called the course search-reindex endpoint on
release, but it returned 403 twice for the named instructor, who had target
course instructor access without Django staff/superuser access. The course was
marked released in modulestore but the UI release flow did not complete. This
is a business FAIL, not an infrastructure or authentication failure. Learner
publication/draft, search and worker behavior, GridFS/File, SCORM/ILT, restart
persistence and D4 were not run to completion on this input. The exact failed
state and logs remain in the delivery59 evidence/private runtime.

Platform `8f31fa2d9eaa4e1deeb2762b143b536a338d9f02` removes the redundant global
role gate and tests own-course instructor permission plus unrelated-course
denial. Delivery60 is the required clean replay; no delivery59 resource is to be
modified or reused for acceptance.


# Python 3.13 internal delivery status

Updated: 2026-10-27 (Asia/Shanghai). Goal active. Local candidate is not complete.

## Active replay: delivery53

Rechecked at the start of this implementation turn. Platform is clean at
`990cdc0d7df7f0a817d026a7ab4e1e23db721e54`; devstack is clean at
`ac9b6af1e924e910b45bc98aca16cf03ada78403`; theme input is
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`. Platform remote delivery remains
`421a93f08fda9f849384ff96525b9ce6e952f962`, while the devstack remote delivery
remains `42b6b945b4bcb6dadbdb06acfe61ddf5fb298202`. Frozen platform refs were
rechecked at master `5c2015893ef357436a36e7590646efb9ab1bb804`,
py313-master `fbb305460bcc9d8ebcb440824de3d976d65063c3`, and py313-wip
`4759a01524b497522910b9035b16c852e70d053f`; none was changed. Devstack has no
local py313-wip ref. No source checkout was modified during D0.

Delivery53 uses a new runtime volume, service volumes/network, SQL and Mongo
databases, loopback ports 18780/18790, and run-scoped cache/search/queue/course
namespaces. Config SHA256 is
`968ef3e589f368ee650604ccbb4dd0a32e07f121de3952fda9a1bf9d4c2cf96b`; its
private secrets/credentials are mode 600. Evidence is retained at
`/Users/noahwang/workspace/hawthorn/py313-delivery53-evidence/`, and the frozen
export at `/Users/noahwang/workspace/hawthorn/py313-delivery53-export/`.

| Gate | Delivery53 result | Evidence / command |
| --- | --- | --- |
| D0 source/resource isolation | PASS | `preflight.json`, `export.txt`, `create-infra.txt`, `create-runtime.txt`; exact commits and config hash above |
| D1 clean dependency install | PASS | `install.txt`: Python 3.13.14, 315 distributions, full `uv pip check`; `installed-source-identity.txt`: all 20 registered sources match installed bytes |
| D2 source reconciliation | IN PROGRESS | wip-only semantic review and current platform commits; all behavior requiring live service evidence remains open |
| D3 fresh schema and LMS/CMS checks | PASS | `initialize-schema.txt`: local-model-sync, 149 apps, 316 models including M2M, 316 tables, historical migration count 0; `lms-check.txt`, `cms-check.txt` exit 0 |
| D3 fresh assets | RUNNING | `npm-ci.txt` and `xmodule-assets.txt` exit 0; Webpack/Sass and locale/static still running |
| D3 browser/business/worker/restart | NOT RUN | Must use this exact paired export; see acceptance matrix below |
| D4 portable independent checkout | NOT RUN | Requires final paired SHAs and delivery instructions |
| D5 local candidate | NOT RUN | No push/PR performed or authorized |

The install command was
`python3.13 replay/run.py --config <private config> install`. It completed exit 0
without `--no-deps`, source skips, exception suppression, or post-install
site-packages edits. `uv pip sync` checked all 315 distributions; the installed
identity verifier checked all 20 committed build trees and their installed
source bytes. The currently running schema command uses the new delivery53 SQL
database and `local-model-sync`; this is development bootstrap, not historical
database migration.

Schema initialized on the new SQL database and checked the actual database
catalog: 149 apps, 316 models including M2M, 316 tables and zero historical
migration records. Site seeding, run-scoped staff/learner creation,
completion-tracking seed and site-theme setup exited successfully. LMS/CMS
`check` both exited 0; LMS reports four Django warnings (`staticfiles.W004` and
three duplicate URL namespaces). Startup also reports one
`openassessment.assessment.HistoricalSharedFileUpload` auto-import miss,
deprecation/SyntaxWarnings and a ResourceWarning. They are retained in the raw
logs and are not represented as a warning-free check. The full-platform
historical-migration path remains explicitly out of scope.

The assets phase is still running. `npm ci --legacy-peer-deps --ignore-scripts
--no-audit --no-fund` and the fresh XModule asset staging have exited 0. npm
legacy-package warnings and Sass deprecations are retained in their output.

## Contract and resources

Native linux/arm64, Python 3.13, Django 5.2; new development databases only.
No production, real IdP, external ORA2 checkout, historical migration edits,
old-runtime writes, push, PR, or subagents. Frozen platform master,
py313-master and py313-wip must retain their initial refs.

Initial platform: `760cafbb90e2148c655a8505fd8ecaf0b4e07940`.
Initial devstack: `42b6b945b4bcb6dadbdb06acfe61ddf5fb298202`.
Theme: `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`; export Git content only.
Remote platform delivery: `421a93f08fda9f849384ff96525b9ce6e952f962`;
remote devstack matches initial local commit (fresh ls-remote).

Delivery51 is a historical diagnostic run, prefix `py313-delivery51`, host ports
18580/18590; SQL `py313_rebuild_delivery51`, Mongo/cache/ES/queue
`py313_delivery51`. The latest diagnostic run is `delivery52` below. Every
environment has its own labeled resources.
Delivery47/48 experiments are stopped with data and logs preserved after OOM;
delivery49/50/51 remain running with their separate data and evidence.
Only environments created by this task were stopped. Older run39/run42 and
replay43-46 remain protected. No resource cleanup was executed.

Runtime export50: platform `8c9f3113a8b` and devstack `4d23167` (full SHAs in
run config and commands.jsonl). Installation failed on an incorrect build-only
lxml constraint; a diagnostic complete install now uses the corrected committed
constraint from `df5fbbc`. This run is not final-candidate acceptance.
Current platform adds fail-closed admin/cookie diagnostics, missing-tab denial,
Python 3 account audit text, scoped visitor and program-export filters through
`306809221d0`; affected runtime checks remain pending.

Private evidence root: `py313-internal-delivery-evidence-20261027` plus each run's
own evidence directory. Final portable sanitized evidence has not been assembled.

## Acceptance matrix

| Gate | Command / expected behavior | Status | Evidence |
| --- | --- | --- | --- |
| D0 source/resources | Git status/HEAD/remotes, refs, Docker and listening ports | PASS delivery52; final pair pending | `delivery52-evidence/config.json`, `preflight.json`, fresh `ls-remote` entries in `commands.jsonl` |
| D1 full dependency closure | New venv; complete graph resolve/install and pip check | PASS delivery52; final pair pending | `delivery52-evidence/install.txt`, `installed-source-identity.txt`: 315 distributions; all 20 registered sources verified |
| D1 SAML contract | LT installed processor/identity contract | PASS offline LT; comparison documented | d1-saml-lt-contract01.txt; SOURCES.md; no IdP |
| D2 reconciliation | Semantic disposition of every wip-only change, especially access/security | IN PROGRESS | Semantic review found and ported missing guards/filters; real runtime checks pending |
| D3 schema/startup | Fresh local-model-sync; complete LMS/CMS app registry and checks | PASS delivery52; final-source replay pending | `delivery52-evidence/initialize-schema.txt`, `natural-sites.txt`, LMS/CMS checks; no historical migration claim |
| D3 browser author/learner | Login; Studio create/edit/publish; learner reads publication | PARTIAL delivery52 | `browser-cms-http-tail52.txt`, `course-state-after-release52.txt`: CMS browser created, edited and released a course. Enrolled learner browser study flow remains NOT RUN |
| D3 permissions | Anonymous, unenrolled, learner, staff, cross-org allow/deny | PARTIAL delivery52 | `course-read-routing52.txt` denies anonymous and unenrolled courseware access; ES permission matrix passes. Full enrolled learner and course-role browser matrix remains NOT RUN |
| D3 delayed publish/draft | First publish after >60s; draft remains private | NOT RUN | Delivery52 timestamps do not establish the required first-publish interval or draft-privacy matrix |
| D3 asset CRUD | Real Mongo/GridFS + SQL agree with HTTP | PARTIAL delivery52 | `mongo-gridfs52.txt`: real save/read/list/sort/page/MIME filter pass. Update/delete and HTTP-to-SQL consistency NOT RUN |
| D3 search/worker | Org filters; published course indexed/searchable by browser/API; real broker worker result | FAIL delivery52 | `publication-worker-index52.txt` search assertion failed; `publication-worker-index-inspect52.txt` found no published course document. CMS worker executed `contentstore.tasks.update_search_index` successfully. `search-matrix52-retry1.txt` and `search-matrix-cms52-retry1.txt` pass permission filters. Discovery connection refused; BLOCKED/out of scope |
| D3 resources/LT | Fresh theme/static/Chinese build; LT/File/SCORM flows | PARTIAL delivery52: builds PASS; business flows NOT RUN | `stage-theme.txt`, `npm-ci.txt`, `xmodule-assets.txt`, `frontend-assets.txt`, `lms-locale-static-resume52.txt`, `cms-locale-static-resume52.txt`; CMS log contains Noto Sans font 404s. SCORM/File/ILT business flows remain NOT RUN |
| D3 restart | Course, assets and learning state persist | NOT RUN | Delivery52 has no before/after restart snapshot |
| D4 independent rebuild | New checkout, portable inputs, documented sequence | NOT RUN | Same host limitation if applicable |
| D5 local candidate | Clean paired commits/manifest, all local gates pass | NOT RUN | Push authorization only after completion |

Failure logs are append-only. Historical run42 is reference evidence only.

## Current implementation checkpoint

Platform `990cdc0d7df7f0a817d026a7ab4e1e23db721e54` includes semantic security,
Mongo, completion/frontend ports, current webpack/lazy translation fixes and the
discussion-permission inheritance fix. The new discussion regression test is
committed; a complete replay of this exact source SHA is pending.
Dedicated resolver experiment used platform `0483b86fafe` and devstack `f7dbb92`;
this is dependency evidence only, not acceptance of the current product SHA.
New arm64 toolchain image: `sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`.
Preserved failures: d1-resolve01 (dangling bind-mount symlink copying),
d1-install01 (unsupported uv flag). Installer fixes are committed before replay.

D3 delivery47: fresh complete installation and pip check PASS; installed-source
identity FAIL: edx-drf-extensions and django-pipeline both install docs/conf.py.
Evidence: delivery47 installed-source-identity.txt; failure preserved.
Registered edx-drf-extensions setup excludes docs and nested tests for next replay.
This is a source packaging correction, with updated frozen setup.py hash.

Runtime import diagnostics (read-only overlays, package environment unchanged):
LMS discovered and fixed per-iteration: current Social Auth exception names,
student app duplicate module identity, Django middleware MRO, edx-search removed
legacy endpoints, Django staticfinder API, invalid `fake2` language. Evidence
`d2-current-import01..17*.txt` retains failures; `d2-diagnostic-export01..12.txt`
retains each source overlay identity. LMS check reached warnings only at import17;
ILT's fixed log handler could not open its directory, addressed in replay schema
preflight before final checks. The current package volume is still the first
experimental install and is not acceptance of the latest paired source.

Delivery48 full install: PASS 315 distributions, pip check and all 20 installed
source identities (platform 39d2bd3bbeac006c024366dddf1cc4c4c7346e1a,
devstack 7be23cf9f87492d97c241bb99c089dba832199a4).
Schema FAIL before initialization: inventory retained edx_jsme, retired in platform
919e976409d1a04b542fc2ee04b3b3b0a6a7cad5. Strict inventory updated; no
historical migrations touched. LT program/mixed HTTP contracts restored from
registered upstream commit instead of conditional URL omission. New replay pending.

Delivery49 installation FAIL: native compilation OOM killed the runtime; xmlsec
build isolation selected unconstrained lxml 6.0.2 while the runtime locks 5.3.2.
Evidence: delivery49 install.txt and d3-resource-bounding01.txt. Build constraint
now fixes lxml 5.3.2, and UV_CONCURRENT_BUILDS=1 bounds native compiler memory.
Only task-created delivery47/48 experiments stopped; all volumes/logs retained.
Older runs remain protected. Portable acceptance helper removes fixed historical
course/block IDs from SCORM/component/ILT scenarios; runtime checks pending.

Delivery50 install FAIL (dependency conflict, not OOM): upstream xmlsec 1.3.17
explicitly pins build-only lxml==6.0.2. Corrected the overly restrictive 5.3.2
build constraint after reading the immutable sdist pyproject.toml; runtime remains
locked at 5.3.2 and both compile against system libxml2. Serial builds retained.

Delivery51 replay input: platform `9a1cfce8c94b7c371ed71bf356e767300773027e`,
devstack `158c36a337a59bdf0de4f14c0884536f289ce3bd`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`; Python 3.13.14; new runtime image
`sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`;
config SHA256 `f1c699d18e1930f8ce4b0180424a9f26a509e00928c6afdb9a87adbbc59f06c9`.
Input preflight, frozen export, 315-package install, `uv pip check`, all 20 source
identities, local-model-sync, full LMS/CMS checks, npm/XModule/webpack/locale/static
builds and HTTP/worker dispatch/readiness passed. Browser LMS/CMS login both passed.
Actual Studio course creation failed while `seed_permissions_roles()` inherited a
`Permission` model instance into `Permission.objects.get_or_create(name=...)`;
Python 3 default stringification exceeds the existing 30-character column and
MySQL rejected the insert. Failure evidence: `delivery51-evidence/browser-course-create-failure.log`.
No course creation or publication pass is claimed for delivery51.

Platform commit `990cdc0d7df7f0a817d026a7ab4e1e23db721e54` now passes the
permission name string when inheriting forum permissions and adds
`common/djangoapps/django_comment_common/tests.py`. `compileall` and `git diff
--check` passed; the full regression run and final environment replay must still
exercise this exact commit. Delivery51 resources and evidence remain untouched.

## Delivery52 diagnostic replay

Input was platform `990cdc0d7df7f0a817d026a7ab4e1e23db721e54`, devstack
`7f4415098f8e69a1826358905d5406601a278ce6`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, runtime image
`sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`,
Python 3.13.14, configuration hash
`3adb432ab5deca11f58e2be357435718657bb16a108939ee53dcb44a05b23634`.
It used new container/volumes/network, host ports `18680/18690`, SQL
`py313_rebuild_delivery52`, Mongo/cache/ES/queue namespace `py313_delivery52`.
See `/Users/noahwang/workspace/hawthorn/py313-delivery52-evidence/config.json`
and `commands.jsonl`. Environment and evidence remain intact; do not write to
Delivery52 again. A new run is required for any changed harness or product SHA.

PASS: clean installation without dependency skipping, 315 distributions,
`pip check`, 20 installed-source identities, local-model-sync new-schema
initialization, full LMS/CMS checks, theme/npm/XModule/webpack/locale/static
builds, LMS/CMS login, browser Studio course create/edit/release, real Mongo
GridFS save/read/sort/page/MIME filter, and LMS/CMS Elasticsearch permission
matrices. These do not close the remaining acceptance gates in the matrix.

FAIL/NOT RUN: published course search returned no course document even though
the CMS worker received `contentstore.tasks.update_search_index` and reported
SUCCESS; direct lookup also returned 404. The failed assertion and inspection
are retained in `publication-worker-index52.txt` and
`publication-worker-index-inspect52.txt`. No Discovery service is registered;
its business task logged connection refused at `0.0.0.0:18381` in
`start_worker-cms` runtime log and is not an internal-delivery pass. Enrolled
learner browser study, delayed first-publish timing, private draft, real GridFS
update/delete, File/SCORM/ILT business flows and restart persistence were NOT
RUN. Current `browser-cms-http-tail52.txt` also contains missing Noto Sans font
requests; this remains a static-resource defect to investigate on the next run.

Diagnostic exception with restoration: while tracing the missing search
document, one probe called `CoursewareSearchIndexer.index` directly against the
Delivery52 ES namespace and wrote three course documents. It then deleted only
those course-matching documents; the final `_count` returned to zero and the
course query to zero, matching the observed pre-probe state. The reindex output
is `publication-indexer-reindex52-diagnostic.txt`; the failed worker assertion
is preserved. This operation was limited to the new Delivery52 namespace and
is not a passing publication result. No further Delivery52 service/database/
search writes are authorized by the run contract.

## Delivery58 infrastructure OOM replay

Delivery58 used platform `7962745ac4d0966442498326b1dad25696ea4c6f`, devstack
`77d6e8774017cbd70f8bbc8e8cd226d5fd5e2f59`, theme
`7c0dbec1b0a79d7639069f9990b831ba9f31d8bf`, runtime image
`sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`,
Python 3.13.14, native linux/arm64, and canonical config SHA256
`f454e0251a88d9e031b7dbf5352dc9ef3f0b747d368eecdd901e2fa0504bbdf9`.

D0 preflight/export/resource creation and D1 complete install passed. All 315
locked distributions installed without dependency bypass; `uv pip check` and
all 20 installed-source byte comparisons passed. D3 local-model-sync built a
fresh development schema (149 apps, 316 models/tables, zero historical
migration rows), both settings checks passed with warnings, and npm/XModule/
LMS/CMS Webpack/locale/static phases exited 0. Each Webpack stats file reported
120 chunks. Evidence remains in
`/Users/noahwang/workspace/hawthorn/py313-delivery58-evidence/`.

The initial Elasticsearch service start exited 137/OOMKilled after its JVM
reported a 256 MiB heap and reached `starting ...`. A direct start of the same
delivery58-owned container also exited 137/OOMKilled. MySQL was found
OOMKilled; starting only that delivery58-owned database container succeeded
and it remained up during a short observation. LMS/CMS HTTP and worker
processes had been dispatched, and the login page returned HTTP 200, but a
browser login submission returned 500 because the down MySQL service name
`mysql` could not resolve. This is infrastructure failure evidence only; no
product authentication conclusion, course flow, search/worker business result,
storage, SCORM, ILT, or persistence pass is claimed for delivery58. Details are
in `delivery58-service-oom.txt`; no old run container/volume/network was
changed.

The 16 GiB OrbStack VM reported about 590 MiB available and only 184 KiB free
swap before the database diagnostic restart. Older runs remain untouched. A
separate Docker Desktop daemon uses an 8 GiB VM. The runtime image archive
copied from OrbStack has SHA256
`20dbfe1562c1c49d5f1492e8094fd7040df09833942c94922de44d02129d3cbe`; all 15
rootfs diff IDs and the parsed image config match, though Docker Desktop assigns
local image ID `sha256:a8c330432ff0e26cc73c7e1cc9b1d04c7c46cbd6b5fe825360ec54660b92256c`
instead of OrbStack's `sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`.
Delivery59 will use that exact local ID and separate resources. No delivery59
preflight or service operation is represented as passed here.

## Verification command corrections

The first host `compileall` swept committed dependency source, including
vendored Python 2 South migrations; it failed on Python 2 syntax outside the
changed harness. A direct unittest invocation from the repository root failed
because the legacy test module imports sibling `run.py`. A subsequent
`python3.9` compile command also used repository-root paths while already in the
`replay/` directory. These command failures are retained here; they are not
product test results. Correct targeted verification used Python 3.13.14 from
the replay directory: 26 tests passed, and `py_compile` passed for every changed
or added harness module. `git diff --check` passed.
