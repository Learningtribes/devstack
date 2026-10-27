# Python 3.13 internal delivery status

Updated: 2026-10-27 (Asia/Shanghai). Goal active. Local candidate is not complete.

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

Current diagnostic run: `delivery50`, prefix `py313-delivery50`, host ports
18560/18570; SQL `py313_rebuild_delivery50`, Mongo/cache/ES/queue
`py313_delivery50`. Every environment has its own labeled resources.
Delivery47/48 experiments are stopped with data and logs preserved after OOM;
only environments created by this task were stopped. Older run39/run42 and
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
| D0 source/resources | Git status/HEAD/remotes, refs, Docker and listening ports | PASS | d0-baseline.json; fresh ls-remote tool capture |
| D1 full dependency closure | New venv; complete graph resolve/install and pip check | PASS delivery48; final candidate pending | delivery48 install.txt, installed-source-identity.txt: 315 distributions, all 20 registered sources verified |
| D1 SAML contract | LT installed processor/identity contract | PASS offline LT; comparison documented | d1-saml-lt-contract01.txt; SOURCES.md; no IdP |
| D2 reconciliation | Semantic disposition of every wip-only change, especially access/security | IN PROGRESS | Semantic review found and ported missing guards/filters; real runtime checks pending |
| D3 schema/startup | Fresh local-model-sync; complete LMS/CMS app registry and checks | FAIL / retry pending | delivery48 schema inventory assertion; updated inventory; no historical migration claim |
| D3 browser author/learner | Login; Studio create/edit/publish; learner reads publication | NOT RUN | Current delivery required |
| D3 permissions | Anonymous, unenrolled, learner, staff, cross-org allow/deny | NOT RUN | Current delivery required |
| D3 delayed publish/draft | First publish after >60s; draft remains private | NOT RUN | Current delivery required |
| D3 asset CRUD | Real Mongo/GridFS + SQL agree with HTTP | NOT RUN | Current delivery required |
| D3 search/worker | Org filters; real broker worker result | NOT RUN | Current delivery required |
| D3 resources/LT | Fresh theme/static/Chinese build; LT/File/SCORM flows | NOT RUN | Current delivery required |
| D3 restart | Course, assets and learning state persist | NOT RUN | Current delivery required |
| D4 independent rebuild | New checkout, portable inputs, documented sequence | NOT RUN | Same host limitation if applicable |
| D5 local candidate | Clean paired commits/manifest, all local gates pass | NOT RUN | Push authorization only after completion |

Failure logs are append-only. Historical run42 is reference evidence only.

## Current implementation checkpoint

Platform `1ed90b7abdc` includes semantic security, Mongo, completion and frontend
ports. Syntax/input consistency passed; runtime acceptance remains NOT RUN.
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
