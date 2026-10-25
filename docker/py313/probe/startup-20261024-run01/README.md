# Python 3.13 local runtime checkpoint

Captured 2026-10-24. The final local combined-input rebuild passed in run39.
This remains a development-only recipe, not a production migration procedure.
Do not run initialization or seed scripts against existing/production databases.

## Verified local entry sequence (run39)

Use Python3.13.14/Django5.2.13, an independent empty /runtime volume and new
py313_rebuild_* MySQL/Mongo/cache/search/queue namespaces. Never point these
initializers at an existing manual database. Protected env values remain
outside Git. Exact image, ports, resources and execution evidence are in
`/Users/noahwang/docs/hawthorn/py313-startup-artifacts-2026-10-24/run-39`.

1. Mount this root read-only at /startup and the current platform source
   read-only at /input/platform. Run install.sh with
   PY313_PLATFORM_SOURCE_ROOT=/input/platform; it creates /runtime/venv and
   a separate writable /runtime/platform-source. No old venv is copied.
2. Run prepare_theme_inputs.py. In the writable platform root run
   npm ci --legacy-peer-deps --ignore-scripts --no-audit --no-fund.
3. Use initialize_local_database.py with a new registered DB, explicit
   PY313_MYSQL_CONTAINER/PY313_RUNTIME_CONTAINER/PY313_SECRET_ENV_FILE,
   PY313_CHECK_RUNNER and a unique PY313_SCHEMA_ITERATION. This invokes
   startup_schema local-model-sync plus full316-model/M2M audit and
   natural-key host Site creation; historical migrations remain0.
4. Run build_xmodule_assets.py through manage.py lms shell using startup_lms.
   Then run **bash /startup/build_frontend.sh** from the writable platform
   root. This exports STATIC_ROOT_LMS/CMS and generates webpack stats in
   both runtime static roots. Running webpack alone without these variables
   does not complete the resource build and causes login500.
5. For each system run build_locale_assets.py and collectstatic. Seed local
   acceptance users/completion only in the new DB. SiteTheme is
   get_or_create by the naturally resolved Site; never replace manual rows.
6. Run both checks and scan for swallowed plugin errors. Start both HTTP
   processes and start_worker.py lms/cms with explicit target env/root;
   workers consume four isolated service-specific queues. Check health and
   browser/business results after dispatch; dispatch alone is not readiness.

Theme source is theme-inputs/7c0dbec1b0a7/hawthorn with per-file verified
manifest. PDF public/build is required runtime code and is retained when
copying patched inputs. PDF authoring rejects non-course-staff before writes.
Seven old calc/chem/opaque constraints are closed by actual compatible source
and metadata, target tests and315-package pip check; see runtime-inputs doc.
Goal status remains in the main docs workspace; this entry is not a production
migration recipe. Preserve all old containers, volumes and data.

## Accepted local runtime and limits

Final inputs: platform31c50d8bcf23efed8e96798a6f0c9289cdc7d9ff,
devstack executable inputs c9606c1a7e7fd992ef8586c22cae3550ed2a4219,
theme7c0dbec1b0a79d7639069f9990b831ba9f31d8bf. run39 empty install,
independent schema/assets, Chrome staff create/edit/release/publish/upload,
ordinary learner SCORM completion, real broker/worker business results and
four-process restart persistence all passed. No post-install source repair.
Exact replay commands/times/exit codes and recovery scope are in run39.

Running container: py313-rebuild-runtime-20261025-run39. LMS loopback18180,
CMS18190. Set PY313_RUNTIME_CONTAINER to that name,
PY313_SECRET_ENV_FILE=/Users/noahwang/.codex/py313-runtime-run39.env and
PY313_PLATFORM_ROOT=/runtime/platform-source before invoking start_http.py or
start_worker.py with lms/cms. Inspect exact processes before starting a second
copy; these scripts dispatch rather than prove readiness. Keep protected
credentials outside Git and evidence. A new reconstruction must use another
empty volume and new namespace/ports, not initialize the accepted database.

Optional Discovery sync fails because its external service is absent; local
Elasticsearch publishing works. The secondary draft-preview link has no
separate preview-LMS configured; primary published LMS preview works.
External IdP/OIDC/SAML, LTI provider/outcomes, XQueue/ORA grading and proctoring
integration remain deferred. Registered LTI consumer OAuth1 signatures pass;
retired DOP is not installed. HS256 issued-token and synthetic RS512/JWKS
proofs are separate. Historical migration records0 and74virtual initial
migration descriptions document local-model-sync only. Existing three LMS
namespace warnings, deprecations and optional shell historical-model import
warning remain disclosed in final acceptance, not silenced.

## Historical runtime checkpoints

## Latest runtime checkpoint (run-26, 2026-10-25)

The current runtime input requires opaque-keys 4.0.0, CCX keys 2.0.2 and
DOT 3.2.0. The older opaque-keys 0.4.4 dependency-closure result did not pass
application setup because completion/events require newer key APIs. A fresh
run-26 volume was installed, incrementally repaired from registered source,
and initialized as `py313_rebuild_run26`: 149 apps, 301 managed models, 315
tables, zero historical migrations applied. Natural-key Site seeding created
new host records and `/runtime/config/site-ids.json`.

LMS/CMS strict checks, mandatory XBlock enumeration, dependency closure,
Sass/theme/webpack builds, both locale/static collections, LMS internal
heartbeat 200, CMS internal signin 200 and real worker ready have evidence.
These are partial runtime results; a final replay of the combined installer
in another empty venv and real browser/business-task acceptance remain open.
See the protected run-26 README for failed attempts and exact limitations.

`install.sh` now invokes `install_verified_runtime_additions.py` for the
registered fs/Poll/JWT/dogapi source repairs and includes python-memcached.
`PY313_PLATFORM_ROOT` controls source-dependent settings/locale paths.
`start_http.py` and `start_worker.py` accept `PY313_RUNTIME_CONTAINER`,
`PY313_PLATFORM_ROOT`, and a mode-600 `PY313_SECRET_ENV_FILE`. The default
remains the preserved startup runtime, so set the target explicitly.
`PY313_TASK_QUEUE_PREFIX` names independent priority queues, exchange and
result keys. Runtime ports come from the protected environment.

## Historical contents (initial checkpoint)

- D01: Dockerfile, local settings, schema inspection/bootstrap/reconciliation,
  seed helpers and HTTP/worker entry points. Schema bootstrap uses model sync;
  migration-state correctness remains unverified. Site IDs and database names
  are specific to this existing local environment.
- D02: installer scripts, dependency inputs and adapted dependency sources.
  Existing source metadata and licenses are retained. Retired DOP inputs,
  upstream tarballs, caches and build metadata are excluded from Git.
- D03: runtime acceptance probes, small fixtures and asset replay scripts.
  These probes are preserved; this commit session did not rerun all probes.

## Required local state and restoration

Secrets remain in .env, .acceptance-credentials.json and jwt-private.pem;
none is committed or included in the checkpoint archives. Supply fresh local
credentials and a local signing key separately when rebuilding.

The protected archive at
/Users/noahwang/docs/hawthorn/py313-commit-artifacts-2026-10-24/run-01/devstack-working-files.tar.gz
preserves nonsecret startup inputs, generated assets, themes and theme-inputs.
Inspect archive member names before restoring into a NEW scratch directory;
never extract over the running checkout. Members are relative to the devstack
repository root. Compare hashes with devstack-file-hashes.json before reuse.
The theme builder currently requires theme-inputs/dce4781ddd25/hawthorn;
Git alone does not restore that copy. See checkpoint-manifest.json for the
source commits. created-resources.json is local resource metadata, not a DB backup.
Older Goal A/B and solver directories remain untouched and outside these commits
and the startup archive. No database or runtime-volume backup was performed.

## Historical remaining gaps (superseded by run39 acceptance)

The old file:///work/patched references are replaced by the registered
writable build-source location. Initial and later dependency-closure checks
pass, but the final combined installer still needs a fresh replay. This is
not yet a complete portable reconstruction recipe. Full authorization/organization/LT and SCORM matrices,
formal schema review, expanded restart persistence, an empty venv with second
isolated databases, and a complete browser rebuild loop remain pending.
HS256 issued-token evidence and the separate RS512 JWKS probe are distinct.
Discussion/wiki strict plugin checks and learner route replay passed on the preserved runtime; final rebuild browser acceptance is still required.

Prior runtime evidence lives under
/Users/noahwang/docs/hawthorn/py313-startup-artifacts-2026-10-24/run-02/.
Never reuse that evidence as proof that each intermediate commit runs alone.

## LT-02 local third-party token exchange rejection

`test_auth_exchange_runtime.py` exercises the production LMS resolver and
`oauth_dispatch` dispatch/decorators, real PSA backends, middleware, exchange
form/adapter and DOT models. `settings/exchange_acceptance.py` is loaded in a
new process before setup, URLs and scope choices are cached. It enables only
this process's third-party-auth flag, appends installed GoogleOAuth2 and
TwitterOAuth backends, uses a private in-memory cache, and shares the
MIDDLEWARE/MIDDLEWARE_CLASSES list so ThirdPartyAuthConfig.ready registers the
real exception middleware for Django 5.2. The default settings stay unchanged.

Nine rejection cases cover missing access_token/client_id, nonexistent client,
real confidential client, invalid scope, OAuth1/unknown backend and GET/PUT.
All other fields use valid local values; the third-party token is an explicit
nonsecret placeholder and must never reach do_auth. An existing ordinary user
is read only as fixture owner. Two DOT applications, per-request anonymous
sessions and pipeline markers are inspected inside SQL transactions and
rolled back; no login, provider config/secret or existing business-row edit is
needed. Anonymous country_code/ip_address session rows are expected; only the
two client rejection cases add auth_entry=login_api. Authentication session
keys, user/token/grant identities and existing session rows must stay unchanged.

Python call profiling fails on do_auth or token issuance; the Python network
audit rejects external DNS/connect/sendto and permits SQL/cache plus loopback
statsd. Native MySQLdb SQL I/O is not a Python socket audit event. This is
Django Client verification, not a browser or network OAuth/IdP success flow.

Use a separately installed runtime containing the three TPA Django 5.2 import
fixes (urls.py, api/urls.py, middleware.py); do not patch or restart run39.
Prepare its registered theme sources and nonsecret site-ids.json mapping.
For a preserved-database replay, the protected env must select the correct
existing local database and the fixture owner must exist. No schema seed is
run against that database. Choose a fresh evidence directory and output label:

```bash
mkdir -m 700 /absolute/path/to/new-run
PY313_RUNTIME_CONTAINER=<separate-runtime> \
PY313_SECRET_ENV_FILE=/absolute/path/to/protected.env \
uv run --no-project python run_auth_exchange_acceptance.py \
  --run-dir /absolute/path/to/new-run --label exchange-01
```

The host runner records command, host/container working directories,
start/end UTC, role, exit status and input SHA256 values; protected env values
are injected by variable name and redacted from captured output. It refuses
to overwrite an existing result. Run41 records the empty-venv installation,
full source identity comparisons, retained failures and final nine-case pass.
Historical browser/schema/task evidence remains separately scoped to run39.
