# GoodHabitz repair and clean replay — 2026-11-02

**Index repair PASS on final R5; full deployment BLOCKED at fresh schema.**
Complete installation and deferred schema SQL passed. Schema initialization then
failed in Django's migration autodetector because
`OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL` is absent. No usable deployment URL exists.
No assets, HTTP/workers, browser, queued-task or restart/persistence acceptance
was reached. Historical migrations and existing-data upgrades were not tested.

## Frozen inputs

Platform `origin/py3-master` was refreshed and remained
`7dcbcca0651875f0b7748216847715e60f3af706` through final remote inspection.
No equivalent title-index PR existed. The independent branch is
`codex/py3-goodhabitz-title-index`; only the invalid nonunique title index is
removed. Title capacity, null/blank values, collation, ordering and business rules
are retained. Existing indexes are not automatically dropped; existing-data
maintenance is a separate follow-up. No initial migration was generated for this
currently unmigrated app, and no historical migration was changed.

Review: [Platform Draft PR #2431](https://github.com/Learningtribes/platform/pull/2431),
targeting `py3-master`; documentation HEAD `e72cffebf6c` adds only the verification
report over the final replayed executable candidate.

Devstack PR #3 was OPEN at
`393de2bc64ec64c62362a010393dcf412ccd85d1`. Its delta from executable adapter
`a72247f2289e2e3435e15c7de47062bcb42f5186` contains only documentation/examples.
All runs use the reviewed committed adapter at `393de2b`, unchanged executables,
and theme `7c0dbec1b0a79d7639069f9990b831ba9f31d8bf` (163 verified files).
These later report/navigation changes were not part of the executable replay.

| Run | Platform frozen commit | Subnet | Loopback mappings | Regression outcome |
| --- | --- | --- | --- | --- |
| master313r3 | `8f913c29ff98b19db648cebeb4ead634d43948ef` | 172.30.234.0/24 | 18282 / 18292 | FAIL: overly strict single-column FK-index assertion |
| master313r4 | `fe833283b0187f0825b559bb9f322e084295c174` | 172.30.235.0/24 | 18283 / 18293 | FAIL: imposed order on truncated long-prefix sort-key ties |
| master313r5 | `1faef434d6fc4487ec2afebf22ec07b82c792d01` | 172.30.236.0/24 | 18284 / 18294 | PASS: final actual-model/MySQL regression |

The application fix is identical across these three candidates; regression
corrections were committed before each new export. Each candidate received a
new full install and new empty volumes/database, network, private inputs and
namespaces. No partial schema was resumed. All three schema commands reached the
same unrelated OAuth setting blocker after deferred SQL.

Runtime repository reference:
`ltdps/edxapp@sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`.
Separately inspected local image ID:
`sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`.
The local selection is linux/arm64. All six infrastructure definitions retain the
reviewed digest lock. No cold pull, AMD64 rebuild or image publication was done.

## Results

| Stage | Result and evidence |
| --- | --- |
| Offline contracts | PASS: 65 adapter tests and 4 Platform companion tests. |
| Targeted syntax/diff | PASS: final changed Python files (2), compileall and git diff checks. |
| Preflight/export/create | PASS all three runs: absent resources, available ports, isolated paths, immutable committed exports; 2261 startup / 8975 Platform entries. |
| Complete install | PASS all three: 331 distributions, full resolution/sync and uv pip check; 20 registered source identities, two +hawthorn.1 companions and ten Platform editables verified. No dependency/version changes. |
| SAML/theme prerequisites | PASS all three: processor contract without external IdP; theme identity verified. |
| Focused final MySQL proof | PASS R5: MySQL 8.4.13, utf8mb4/utf8mb4_unicode_ci; actual model's former deferred full-title index reproduces 1071; candidate creates all five GoodHabitz models, FKs, indexes and composite unique constraints. |
| Title data/query proof | PASS R5: 1024 four-byte and accented characters, >768-character titles, null, blank, duplicate values; full-value collation lookup and default/explicit/joined order queries. Long-prefix tie caveat below. |
| Fresh schema phase | FAIL all three at migration autodetection after deferred SQL. R5 read-only state: 329 tables, zero applied historical migrations; GoodHabitz constraints present, title index absent. Full schema audit/reconciliation was not reached. |
| Existing GoodHabitz selectors | BLOCKED / FAIL before execution. 213 tests collected. R3 lacked test DB permission. After a task-only test-database grant, R4 and R5 stopped at urls.E007 for render_403/render_404 handler signatures. No check was silenced. |
| LMS/CMS checks and seeding | BLOCKED / NOT RUN: schema phase exited before natural Sites/users/themes seeding and both check commands. |
| Real assets | BLOCKED / NOT RUN: no npm-ci, XModule, webpack, locale or collectstatic. |
| HTTP and actual workers | BLOCKED / NOT RUN: services were not dispatched; mapped ports are not usable URLs. |
| Browser / task / persistence | BLOCKED / NOT RUN: no login/authoring/learner/authorization smoke, real queued-task or restart proof. |
| Integrity only | PASS final R5: original export identities unchanged, 8975 runtime source entries/ten editables verified, seven selected images and ownership checked; evidence scan found no protected values/patterns. Full worker/business audit NOT RUN. |

MySQL's default session `max_sort_length=1024` ties titles differing after 900
shared characters. The first regression incorrectly assumed a deterministic
late-character order. Final proof records the observed default tie behavior and
checks full-title/joined ordering with only the disposable probe session's sort
key enlarged to 8192, restoring it in finally. No application/global sorting
setting changed. InnoDB may replace a redundant FK index with a composite unique
index having the same leading column; final introspection accepts that coverage.
The focused proof uses a separate `_goodhabitz_probe` database, never replay data.

The first R3 probe was invoked before theme staging and failed during settings
import without touching its database; after the normal schema prerequisites it
ran under a new evidence label. No installed sources were edited. A later
accidental repeated test-grant invocation was rejected by the existing exclusive
output-label guard before any mutation. Neither is an application acceptance pass.
An unscoped host syntax scan also exposed the unchanged Python 2 print in
`common/lib/sandbox-packages/eia.py:94`; the required changed-file syntax scan
passed. No historical failure-list expansion or repair was attempted.

## First unrelated blocker and next scope

Failing entry point (each run, exit 1):

```sh
uv run --no-project --python 3.13 python -B \
  docker/py313/probe/startup-20261024-run01/replay/replay_after_install.py \
  --config /absolute/new-run/config.json schema
```

`initialize-schema.txt` ends in Django `migrate.py` calling
`autodetector.changes(...)`, then `_resolve_dependency` reads an absent setting:

```text
AttributeError: 'Settings' object has no attribute 'OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL'
```

The next separate repair should inspect the registered legacy OAuth models'
swappable settings and the reviewed LMS/CMS union schema contract, then validate
the smallest settings/model-compatibility correction on another committed,
empty-volume run. Do not skip migration autodetection or weaken inventory/index
checks. The independently observed URL-handler signature errors remain separate
runtime/test blockers. No OAuth/URL/dependency fix was made in this task.

## Evidence, retained resources and boundaries

[Sanitized command outcomes, durations, log hashes and identities](current-replay-20261102.json)
record each command using its `output` filename. Full argv/traces remain private
under `/Users/noahwang/workspace/hawthorn/py313-master-replay-r{3,4,5}-20261102/evidence/`.
R5 configuration SHA256:
`bc39b6fb0f85988218573d156460bba75f63502b117ff025b2fbdf9c642c715f`.
No raw private logs, full private configuration, credentials or JWT keys are published.

All 211 containers present at the start remain present. `local313-runtime` retains
its `2026-10-29T02:18:05.638782759Z` start time and ports 18000/18010. R1/R2 data
and all prior environments remain. Delivery Devstack's uncommitted binary diff
still hashes to `33c3bc9a6f5d71cef5f45ba6c1fdf6fae8911454c05538444cc5c87d7ea4f822`.
Primary Platform/master and PR8 planning artifacts were not modified. Each new
run retains its seven containers, five data volumes, network and probe database.

Host capacity started with 132 GiB free and Docker memory 15.66 GiB; 125 GiB
remained before final R5 installation completed. No capacity was reclaimed by
pruning or stopping old environments. PR1–PR8 remain closed in scope. No merge,
external deployment, image/package publication or branch-policy change occurred.
PR #3 had no remote checks at initial inspection; that is not CI success.
