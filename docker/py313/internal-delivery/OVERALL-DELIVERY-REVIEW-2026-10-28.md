# Python 3.13 internal delivery overall review

Date: 2026-10-28 (Asia/Shanghai)

This is a read-only review of the current paired worktrees and delivery67 evidence. No service was started, no production or real IdP/ORA2 was accessed, and no historical migration was changed.

## Status

The current state is **local delivery candidate incomplete**.

- **Local delivery candidate complete:** No. D3 business acceptance, D4 independent checkout rebuild and D5 candidate manifest/release boundary are open.
- **Ready for team release:** No. The paired branch is not yet a releasable team input because Elasticsearch/search is unavailable and the remaining business matrix has no current-candidate evidence.
- **Overall Python 3.13 migration complete:** No. The branch contains a large Python 3.13/Django 5.2 migration series, but historical requirements, unverified callers and production migration concerns remain.

The latest valid evidence identity is delivery67:

| Input | Value |
| --- | --- |
| platform | `py313-delivery-20261027` at `36d1a28ec7dfe85c6036fd52bd82c926fc2492ec` |
| devstack | `py313-delivery-20261027` at `5ba565fb7d5792b5636a15f254b73a8e8d2587f4` at replay time |
| theme | `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf` |
| target | native `linux/arm64`, Python `3.13.14` |
| evidence | `/Users/noahwang/workspace/hawthorn/py313-delivery67-evidence/` |

The local devstack worktree now has documentation commit `5115c7ea7fffb9ed62459f48334d586cd17be90b`; any new replay must use this newer exact pair and record a new evidence identity.

## Branch and worktree inventory

| Repository | Current branch / HEAD | Base | Delta |
| --- | --- | --- | --- |
| platform | `py313-delivery-20261027` / `36d1a28` | `master=5c201589` | 362 commits, 1,565 changed paths |
| devstack | `py313-delivery-20261027` / `5115c7e` | `master=8be6766e` | 117 commits |
| frozen platform refs | `py313-master=fbb3054`, `py313-wip=4759a01` | must remain unchanged | reference only |
| historical branches | `py313-local-env`, `codex/py313-replay-parameters-20261025` and older `py313-*/wave-*` | historical | not current delivery inputs |

The platform remote delivery ref previously observed was `421a93f`, behind the local platform HEAD. Re-check `git ls-remote` immediately before any publication; no push was performed.

Complete, auditable commit ledgers:

- Complete platform ledger: `/Users/noahwang/docs/hawthorn/py313-platform-master-commit-ledger-2026-10-28.tsv` — all 362 commits.
- Complete devstack ledger: `/Users/noahwang/docs/hawthorn/py313-devstack-master-commit-ledger-2026-10-28.tsv` — all 117 commits.

The ledgers are generated from `git log --format='%H%x09%ad%x09%s' --date=short master..HEAD`; they are the complete list, while the sections below group the changes by responsibility.

## Platform changes relative to master

The 362 commits are a migration series rather than a single delivery patch. The changed paths are concentrated in `lms` (590), `common` (387), `openedx` (305), `cms` (202), `themes` (22), `scripts` (18), and `requirements` (12). The major groups are:

1. **Python 3.13 syntax/runtime:** Python 2 exception, octal and print syntax; tuple parameters; iterator/Unicode/bytes/URL/stdlib contracts; removed unittest/nose APIs; test collection and import fixes.
2. **Django 5.2 framework contracts:** translation/encoding APIs, `MIDDLEWARE`, `django.urls`, `request.is_ajax` removal, timezone APIs, `STORAGES`, removed storage loader, model/index compatibility, settings/template origin APIs, SameSite cookies, exception arguments, static finder keyword arguments and password reset.
3. **Auth and API:** Django OAuth Toolkit-only runtime, retired OAuth provider removal, modern DRF and `drf-yasg`, URL namespace/detail-route fixes, SAML IdP and ORA2 compatibility, LTI token/Celery 5 contracts.
4. **Storage and Mongo:** PyMongo 4 client/operation lifecycle, contentstore and program-enrollment callers, GridFS cleanup ordering, boto3/django-storages 1.14, overwrite backend replacement, report/video storage and Unicode download paths.
5. **Search and permissions:** provider endpoint registration, published-course reindexing, course-author reindex authorization, discussion permission names, organization/visitor boundaries and fail-closed diagnostics.
6. **Frontend and assets:** Sass/pipeline compatibility, locale catalog inputs, Webpack stats/lazy translations, theme static finder calls, XModule/frontend/locale/static build paths.
7. **Test and delivery support:** focused CMS regressions, compile/check scripts, source identity checks, and delivery verification documentation.

The final two product-facing commits are `aed8961` (course-author reindex test isolation) and `36d1a28` (Studio Logs Python 3 rendering). They explain why delivery62/63 evidence cannot be reused as current acceptance without a fresh replay.

## Django 5.2 and dependency/pin reconciliation

The migration is represented in source commits and in two different requirement layers. The internal delivery lock is the D67 installation input; legacy repository requirements are not proof that the whole graph has been modernized.

| Dependency/contract | master baseline | current delivery input | Evidence / interpretation |
| --- | --- | --- | --- |
| Django | 1.11.15 | 5.2.13 in platform internal runtime lock | D67 installed 315 distributions and passed `uv pip check` |
| Celery/Kombu/amqp | 3.1.25-era | 5.6.3 / 5.6.2 / 5.3.1 | `django-celery` removed; task discovery restored |
| PyMongo | 2.9.1 | 4.19.0 | callers migrated in Mongo/contentstore/program-enrollment groups; real Mongo business evidence remains open |
| Elasticsearch client | 1.9.0 | 7.17.13 application client | server image is Elasticsearch 8.19.0; search path is not accepted until live service works |
| django-config-models | 0.1.8 | 3.0.0 | Django 5 model/config compatibility commit |
| django-storages | 1.4.1 | 1.14.6 | boto3 storage migration |
| REST/swagger | django-rest-swagger 2.2.0 | DRF 3.17.1 plus drf-yasg | internal `runtime-public.in` still lists legacy `django-rest-swagger`; resolve before release |
| SAML/XML | python-saml 2.4.0, defusedxml 0.4.1 | python3-saml 1.16.0, defusedxml 0.7.1, xmlsec 1.3.17 | offline SAML contract passed in D67 |
| AWS/XML/runtime | boto3 1.4.8, botocore 1.8.17, lxml 3.8.0 | boto3/botocore 1.42.97, lxml 5.3.2 | storage and XML callers updated |
| retired packages | edx-oauth2-provider, PyContracts, django-celery | removed from active runtime | production data/migration implications remain out of scope |

**Pin closure issue:** platform `requirements/py313-internal/runtime-public.in` records Django 5.2.13 and Celery 5.6.3, while devstack `docker/py313/requirements-infra.txt` records Django 5.2.18 and Celery 5.6.2. The latter is an infra/build venv, but the two files are easy to confuse and currently do not describe one exact runtime closure. Before D4/D5, choose ownership and align or explicitly separate these inputs, then rerun install/source identity and record the resulting lock SHA.

## Devstack infrastructure and service changes

The devstack branch adds a Python 3.13 runtime/replay harness, immutable infrastructure locks and delivery evidence. Current service images are digest-pinned:

| Service | Current image/version | Change |
| --- | --- | --- |
| MySQL | 8.4.13 | utf8mb4 server defaults and healthcheck |
| MongoDB | 8.0.34 | modern `mongosh` healthcheck |
| RabbitMQ | 4.3.7-management | transient nonexclusive queue policy; separate `noperm` pidbox profile |
| Elasticsearch | 8.19.0 | modern server and healthcheck; startup remains memory-sensitive |
| Memcached | 1.6.45 | digest-pinned cache |
| Valkey | 8.1 | replaces the Redis service in compose |
| runtime | Python 3.13 slim bookworm, Node 16.20.2, uv 0.11.23 | separate infra/native probe wheels and application venv |

The replay harness parameterizes ports, databases, network ranges, namespaces, volumes and secrets; freezes platform/theme inputs, exports per-file hashes, rejects resource collisions, uses `local-model-sync` for a fresh development schema, and records commands/evidence. This is a strong D0/D1 foundation, but it does not replace D3 business acceptance.

## Delivery67 evidence and blockers

D67 passed:

- exact paired input/resource preflight;
- complete 315-distribution install and `uv pip check`;
- all 20 registered source identities;
- fresh schema: 149 apps, 316 models/tables, zero historical migration rows;
- LMS/CMS checks, SAML offline contract;
- theme/npm/XModule/frontend/locale/static builds; both Webpack builds emitted 120 chunks.

D67 failed:

- Elasticsearch exited 137 with `OOMKilled=true` under a 2 GiB container and 3 GiB memory+swap limit, despite `-Xms256m -Xmx256m`.

This proves a cgroup/container-level memory kill, not the independent root cause of host pressure. The old replay history also shows host swap pressure in earlier runs, but that evidence is not a D67 diagnosis. Do not restart or reuse D67 resources.

Minimum next memory investigation on a fresh run:

1. Record host memory/swap, Docker/OrbStack VM limits, cgroup `memory.max`, `memory.current`, `memory.events`, container inspect state and ES logs before/after startup.
2. Run one controlled matrix: 2 GiB/3 GiB with 256 MiB heap, then a larger container allowance or lower heap only if the host has measured headroom.
3. Keep the ES server/client compatibility pair fixed while diagnosing; otherwise the run changes two variables.
4. Accept search only after cluster health, index creation, worker indexing and LMS/CMS result plus organization-isolation assertions pass.

## D0-D5 gate status

| Gate | Current status | Required closure |
| --- | --- | --- |
| D0 paired sources/resources | PASS for D67 identity | re-run for the post-doc exact pair |
| D1 dependency/source closure | PASS for D67 lock, with pin ownership conflict above | align infra/application inputs and rerun |
| D2 semantic reconciliation | PARTIAL | finish caller-by-caller Mongo/storage/search/auth ledger and explain every remaining legacy pin |
| D3 core business acceptance | BLOCKED/NOT RUN on current candidate | fresh ES diagnosis, then browser authoring/publish/learner, permissions/org, worker/search, GridFS/File, SCORM, ILT and restart |
| D4 independent checkout rebuild | NOT RUN | build from a clean checkout using only committed/portable inputs |
| D5 candidate/release boundary | NOT RUN | freeze pair, manifest, evidence index and release notes; no push until separately authorized |

Historical delivery59-64 failures and delivery67's OOM are accurate when tied to their own input SHAs. They must remain immutable history. Any status statement that says “assets/schema/install passed” without naming delivery67 and its exact pair is incomplete; any statement that says “delivery complete” is stale or overbroad.

## Priority plan

**P0 — make the current candidate reproducible.** Reconcile the application and infra pin ownership, record the exact lock/source hashes, and produce a new D67 successor identity. Do not inherit old resources or old business evidence.

**P1 — close D2 and diagnose search.** Finish the semantic ledger for Mongo/storage/search/auth/organization boundaries. Run the fresh ES memory matrix with cgroup and host diagnostics; preserve all failed logs.

**P2 — execute D3.** After search starts, run the required browser and real-service matrix on fresh resources. Every assertion must point to the new evidence root; previous delivery56/59/64 evidence remains historical.

**P3 — execute D4.** Create a clean independent checkout, build the runtime image, install from the committed inputs, initialize a new development database and reproduce the documented checks. State the same-host limitation if no second host is available.

**P4 — execute D5.** Freeze exact platform/devstack/theme/image/lock SHAs, update the manifest and status matrix, commit release-boundary docs, and report “local delivery candidate complete, pending publication.” Push/PR/release is a separate authorized action.

Concrete validation standards:

- `git diff --check` and clean worktrees for both repositories;
- one exact pair recorded in manifest, status and evidence preflight;
- `uv pip check`, installed source identity and full dependency report;
- ES cluster health plus published search and org isolation;
- browser evidence for Studio create/edit/publish, delayed first publish, draft privacy, learner completion and permissions;
- real Mongo/GridFS/File CRUD, worker result, SCORM and ILT evidence;
- restart persistence;
- independent checkout replay with no author path, old venv, old volume or old replay evidence.

## Source paths

- Plan: `py313-internal-delivery-plan-2026-10-27.md`
- Current status: `/Users/noahwang/workspace/hawthorn/devstack-py313-delivery-20261027/docker/py313/internal-delivery/STATUS.md`
- Acceptance matrix: `/Users/noahwang/workspace/hawthorn/devstack-py313-delivery-20261027/docker/py313/internal-delivery/ACCEPTANCE-MATRIX.md`
- Replay history: `/Users/noahwang/workspace/hawthorn/devstack-py313-delivery-20261027/docker/py313/internal-delivery/REPLAY-HISTORY.md`
- D67 evidence: `/Users/noahwang/workspace/hawthorn/py313-delivery67-evidence/`
