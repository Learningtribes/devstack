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

Reserved run: `delivery47`; project/network prefix `py313-delivery47`.
LMS/CMS loopback ports: 18500/18510. All service containers/volumes will use
that prefix, SQL `py313_rebuild_delivery47`, test SQL
`test_py313_rebuild_delivery47`, Mongo `py313_delivery47`, cache/ES/queue
`py313_delivery47`. Resource preflight must reject any existing target.
Existing resources, including run39/run42 and replay runs43-46, are protected.
Host has 435 GiB free at baseline. Evidence captured in private local
`py313-internal-delivery-evidence-20261027/d0-baseline.json`; a portable
sanitized evidence summary will accompany the final candidate.

## Acceptance matrix

| Gate | Command / expected behavior | Status | Evidence |
| --- | --- | --- | --- |
| D0 source/resources | Git status/HEAD/remotes, refs, Docker and listening ports | PASS | d0-baseline.json; fresh ls-remote tool capture |
| D1 full dependency closure | New venv; complete graph resolve/install and pip check | PASS (experiment); final replay NOT RUN | d1-resolve02.txt, d1-install02.txt: 315 distributions; registered identity replay pending |
| D1 SAML contract | LT installed processor/identity contract | PASS (LT only); comparison pending | d1-saml-lt-contract01.txt; no IdP |
| D2 reconciliation | Semantic disposition of every wip-only change, especially access/security | NOT RUN | Prior heuristic TSV is a clue only |
| D3 schema/startup | Fresh local-model-sync; complete LMS/CMS app registry and checks | NOT RUN | No historical migration claim |
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
