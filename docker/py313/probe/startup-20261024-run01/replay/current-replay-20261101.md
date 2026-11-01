# py3-master clean local replay — 2026-11-01

**Result: complete installation PASS; fresh schema FAIL. No working deployment is
claimed.** No LMS/CMS checks, assets, HTTP/workers, browser, task or persistence
acceptance was reached. This is a fresh local model-sync attempt, not an old-data
upgrade or historical migration replay.

## Frozen inputs and changes

- Platform fetched `origin/py3-master` and frozen at
  `7dcbcca0651875f0b7748216847715e60f3af706`; no executable delta from the handoff
  target. PR8 #2430 was OPEN and documentation-only; it was not a prerequisite.
- Devstack base `e19e059cc7091d435dd5121b586da0d525a350c5` on an independent
  `codex/py313-py3-master-devstack` worktree. R1 used adapter
  `ee8e858a47529f32a34ca6a33f635c3e92283538`; final R2 used
  `a72247f2289e2e3435e15c7de47062bcb42f5186`. Later commits only add documentation
  and evidence. No Platform PR or package/version change was needed.
- Theme `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf` (163 verified source files).
- Reused local linux/arm64 application image repository reference
  `ltdps/edxapp@sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`.
  The separately inspected local image ID is
  `sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`.
  Python 3.13.14, uv 0.11.23, Node 16.20.2, npm 8.19.4. Cold pull/AMD64 not tested.
- Reused all six locked service image definitions, local settings/schema tools,
  theme/asset procedures and HTTP/worker startup tools. Application source,
  venvs, databases, service volumes, secrets and generated outputs were new.

The install adapter replaces the historical upstream-only installer with Platform
`image-inputs.py` → `install.py` → `verify-platform-identity.py`. Original exports
stay read-only; only task-owned staging is writable. Full resolution/sync/check,
source/companion identity, ownership, export pinning and collision guards remain.

R1 stopped **before schema DDL** because the old inventory omitted five registered
apps. Read-only LMS/CMS registry probes identified three retained legacy OAuth
schema apps, edx_jsme and audience_targeting; CMS also now registers django_countries
and no longer registers oauth_dispatch. The union adds exactly five labels.
R2 explicitly updates the inventory and local-model-sync migration-disable list;
the complete app-set equality guards remain unchanged. R1 was retained; R2 used
new config, exports, empty volumes, databases, network, credentials and ports.

## Actual verification

| Stage | Result / evidence |
| --- | --- |
| Offline guards | PASS: 65 replay tests, including staged input conflicts, wrong lock/missing current contract, failed subprocess propagation, read-only mounts and export/ownership guards; 4 real Platform companion tests reject corrupt archives/base/projected locks. |
| Syntax/diff | PASS: targeted Python 3.13 compileall and git diff checks. |
| Host capacity | Docker ARM64, 15.66 GiB memory; 197 retained containers measured about 1,523 MiB combined; filesystem 137 GiB free before the attempt. No historical resources reclaimed. |
| Preflight/export/create | PASS both runs. New ports/subnets/resources verified; immutable Git exports include 2,257 startup files and 8,974 Platform entries. Real repeated R1 preflight rejected occupied resources. |
| Full installation | PASS both runs: 331 distributions, ordinary full sync and uv pip check. R1 install 185.180 s; R2 214.809 s. All 20 registered build/installed sources, both companion archive/version/origin/bytes and ten Platform editables verified. |
| SAML/theme pre-schema | PASS both runs; processor signatures and theme bytes verified. No real IdP contacted. |
| Fresh schema | R1 FAIL inventory guard, corrected in adapter. R2 FAIL MySQL 1071 during deferred SQL after 17.516 s. Partial schema: 329 tables; zero historical migrations applied. Full model/index audit not reached. |
| LMS/CMS checks | BLOCKED / NOT RUN: schema did not complete; natural Sites and acceptance users were not seeded. |
| Real assets | BLOCKED / NOT RUN: npm/XModule/webpack/locale/collectstatic were not executed. No old generated assets reused. |
| HTTP/workers | BLOCKED / NOT RUN: processes not dispatched. Port mappings alone are not readiness. |
| Browser/task/persistence | BLOCKED / NOT RUN: login, Studio authoring, learner access, authorization, queued task and restart/persistence not tested. |
| Final integrity | PASS: unchanged original exports, 8,974 runtime Platform entries and ten editables, seven selected image/ownership identities, private evidence secret-pattern/value scan. Full worker/business audit not run. |

See [sanitized command outcomes and durations](current-replay-20261101.json) and
[repeatable commands](current-py3-master.md). Exact argv, exit codes, UTC start/end,
config/source identities and detailed redacted logs remain private in each run's
`evidence/commands.jsonl`. No credentials, JWT key, full package metadata or raw
private logs are committed.

## First application blocker and focused follow-up

`lms/djangoapps/goodhabitz/models.py:59` declares a 1,024-character title with
`db_index=True`. Read-only model-generated DDL and constraint introspection show
the first absent deferred statement:

```sql
CREATE INDEX `goodhabitz_container_title_60521c27`
ON `goodhabitz_container` (`title`)
```

The database is `utf8mb4 / utf8mb4_unicode_ci`: the field can require 4,096 index
bytes, exceeding MySQL's 3,072-byte limit. The model diff from the historical
Platform source pair adds this title index. No field/index, charset, dependency,
validation guard or installed package was changed to get past it. There was no
schema resume or repair after this application error.

**Follow-up task: make the GoodHabitz title index compatible with MySQL utf8mb4.**
Reproduce from the fixed Platform SHA with model-generated DDL; review the intended
lookup/ordering behavior, implement a focused Platform model/new-migration change,
and verify fresh MySQL schema/index creation with the same character set and
representative long Unicode titles. Do not edit historical migrations or shorten
catalog data silently. After review, run a new clean replay through checks, real
assets, HTTP/workers, browser/queue/persistence. Do not expand this task to the
historical 47-failure matrix.

## Retained local resources and boundaries

R2 uses `master313r2-runtime`, network `master313r2-network`
(`172.30.233.0/24`), SQL `py313_rebuild_master313r2`, Mongo
`master313r2_mongo`, task/cache/search prefixes containing `master313r2`, and five
new `master313r2-*-data` volumes. Six service containers use the same run prefix.
Loopback mappings are 18281/18291; **no working LMS/Studio URL is available**.
R1's corresponding resources remain under `master313r1` on `172.30.232.0/24`
with mappings 18280/18290. Both failed runs and their partial data are retained.

Private roots:

- `/Users/noahwang/workspace/hawthorn/py313-master-replay-20261101`
- `/Users/noahwang/workspace/hawthorn/py313-master-replay-r2-20261101`

All 197 pre-existing container names are still present; `local313-runtime` remains
running with its original 2026-10-29 start time and ports 18000/18010. Original
Devstack Dockerfile/Makefile/README uncommitted changes are unchanged: binary-diff
SHA256 `33c3bc9a6f5d71cef5f45ba6c1fdf6fae8911454c05538444cc5c87d7ea4f822`.
Primary Platform/master, PR6/PR7/PR8 worktrees and uncommitted planning artifacts
were not edited. No old resources cleaned, no merge, external deployment, CI
rollout, image/package publication or branch-policy change. Stop at Draft PR review.
