# Explicit local replay

Latest result: [2026-11-02 GoodHabitz repair / clean replay](current-replay-20261102.md).
Index regression passed; deployment remains blocked at the next OAuth schema setting.
The [2026-11-01 R1/R2 report](current-replay-20261101.md) remains historical evidence.

For current py3-master, start with [the complete-profile guide](current-py3-master.md)
and [configuration example](current-config.example.json).

Run these host scripts with Python 3.13 (`uv run --no-project --python 3.13 python -B`).
Every entry requires `--config /absolute/path/to/config.json`. There is no selected
container, evidence directory, course, or namespace fallback. Retained historical
run scripts are evidence/examples, not entry points for a new replay.

## Configuration contract

`core.REQUIRED` is the exact JSON key set. Provide these values explicitly:

| Group | Fields |
| --- | --- |
| Identity | `run_id`, `platform_repo`, `platform_commit`, `devstack_repo`, `devstack_commit`, `theme_commit` |
| New absolute paths | `evidence_dir`, `export_dir`, `secret_env` |
| Protected read-only mounts | `credentials_file`, `jwt_file` (regular files, mode 600) |
| Runtime resources | `runtime_container`, `runtime_volume`, `network`, `network_subnet`, `lms_port`, `cms_port` |
| Namespace | `database`, `test_database`, `mongo_database`, `cache_prefix`, `es_prefix`, `queue_prefix`, `course_key` |
| Infrastructure | `services`: explicit `container` for mysql/mongo/rabbitmq/elasticsearch/memcached/valkey, plus `volume` for the first four |
| Images | `images`: six services must exactly match `infrastructure-images.lock.json`; `runtime` is either a local `sha256:<64 hex>` image ID or exactly `ltdps/edxapp@sha256:<index digest>` from `runtime-image.lock.json` |

All resource and namespace names must contain `run_id`. `network_subnet` is a
dedicated RFC1918 IPv4 `/24`; preflight rejects overlap with any current Docker
network and creation binds the exact range instead of relying on Docker Desktop's
default pool. Select a range that also does not overlap the host's routed LAN/VPN
networks. SQL database names start
with `py313_rebuild_` because this is the existing local model-sync initializer.
The course key is a complete opaque `course-v1:` key containing the run id. Ports
are host loopback mappings to the fixed internal LMS/CMS ports 18000/18010.
The export and evidence directories must be new and separate from protected env.
After resolving symlinked ancestors, each output path must also be disjoint from
both source checkouts; evidence, export, and secret-env paths cannot alias or
contain one another. Protected credentials/JWT inputs must be disjoint from each
other and all outputs after path resolution. Output paths must be disjoint from
both source checkouts. Protected inputs may use existing private fixture paths;
the exporter copies committed sources only. Existing broken output symlinks are
rejected as occupied.

`provision-secrets` creates only six random service secrets in a new protected
file. Namespace values cannot appear in this file and cannot override the JSON
contract. Existing `PY313_*` host environment values are discarded.
The generated Elasticsearch service uses a bounded 256 MiB JVM heap; raise it
only after sizing the complete host/container memory budget.

## Execution order

With an explicit operator-created JSON config, run `run.py --config ...` with:

1. `provision-secrets` (refuses an existing file).
2. `provision-acceptance` after creating the identity file's parent as a new
   mode-700 directory (refuses to overwrite credentials). Generate the private
   JWT key separately in the same protected directory and keep both files mode
   600. Passwords and private key material are not printed.
3. `preflight` (read-only dry check; containers/volumes/networks, ports, paths,
   private mounts, source HEAD and tracked cleanliness).
4. `prepare` (rechecks, creates evidence, exports committed sources only).
5. `create` (rechecks physical resources, creates a new network and fresh service
   data, then a new runtime volume/container).
6. `install` (stage the replay tooling, let Platform prepare the current
   application/Paver/test profile, then full resolution/sync/check in an empty venv).
   The old `install_internal_delivery.py` and registered-source installers are
   removed. Platform `ci/py313/image-inputs.py` verifies its companion archives,
   application lock and `runtime-public.in` pins; `install.py` checks the installed
   companions and git pins of all 20 formerly vendored sources. The replay then independently checks all
   Platform bytes/symlinks and ten editable locations. Reports, receipt and both
   complete/resolved locks are captured privately; no package is injected later.

Original exports are mounted read-only at `/paired-startup`, `/input/platform`
and `/canary` (the latter is the exported Platform CI directory). `/startup` is
an initially empty task-owned container staging directory except for the two
protected read-only credential/JWT mounts. Staging runs `/canary/bringup/prepare_current_install.py`: it copies the
Platform-owned bring-up scripts (`/canary/bringup`), then the committed paired replay tools,
without overwriting these mounts or any Platform file; the Platform preparer writes `/input/ci.lock` in the container layer. `/edx/app/edxapp` (the application root of Platform `ci/py313/layout.py`: code `edx-platform`, venv `venvs/edxapp`,
generated outputs `py313/`; `/runtime` is retired) is a
new empty named volume for the application source copy, venv and generated
outputs. Neither exports nor a historical runtime is writable or reused.
Missing current tooling, corrupt inputs, occupied staging/runtime/lock, failed
subprocesses and source/export drift abort; there is no old-lock fallback.

MySQL initialization also grants `edxapp` the configured `test_database` (`replay/mysql-grant-test-database.sh`,
mounted into `/docker-entrypoint-initdb.d`), so `run.py ... test` can create and drop the Django test database.

Then `replay_after_install.py --config ... schema`, `assets`, and `services`.
The schema phase uses fresh local model synchronization, not historical migration.
The assets phase uses `build_frontend.sh` with a 2 GiB Node heap and no
development source maps; both LMS and CMS webpack stats must still report the
expected login bundle. Locale and static collection run after that build.
After the schema phase, run the run-scoped `seed_acceptance_users.py` through the
LMS settings. Use a browser for Studio course creation/edit/release and the
enrolled learner flow; do not treat the seed helper or HTTP readiness as browser
acceptance. After browser authoring, `seed_rebuild_course_acceptance.py` assigns
the named account a course-scoped instructor role (without Django staff or
superuser access), enables the registered plugins, and enrolls the learner.
`test_scorm_socket_runtime.py` then exercises routed multipart upload, role
denials, ordinary learner SCORM commits and per-user state isolation.
`probe_content_assets.py` covers real GridFS create/read/update/delete,
sorting/pagination and MIME filtering. Capture persistence before restart with
`snapshot_delivery_before_restart.py`; restart only the owned runtime services,
then verify the persisted course/assets/learning state with
`verify_delivery_after_restart.py`.

The whole sequence, plus course authoring, a superuser and an HTTP smoke, is automated by
`new_run.py` and `bring_up.py` (`make py313-up`), with `status.py` and the operator teardown
`destroy_run.py` (`make py313-status` / `make py313-destroy`); see the quickstart in
[current-py3-master.md](current-py3-master.md). Teardown is deliberately outside the stages above:
it removes only resources named in the config that carry its ownership label.

`run_check.py --config ... lms <unique-label> check` runs a bounded manage command.
It also supports CMS and explicit registered settings such as `startup_schema`.
`run.py --config ... test cms <unique-label> <Django-test-selector>` runs a
targeted CMS test with the Python 3.13 legacy nose adapter, the replay's isolated
runtime, database and authenticated local Mongo test namespace. LMS tests use
the same form with `lms`. The command and output are captured under the supplied
unique label. The test adapter honors the replay's `PY313_PLATFORM_ROOT` instead
of depending on a platform source path from another container.
`shell.py --config ... lms|cms` (or `make lms-shell` / `make cms-shell` /
`make studio-shell`; the development environment by default, `PY313_CONFIG=/absolute/path/to/config.json`
for another run) opens an interactive bash in the run-owned runtime container. It has no label: a terminal session is not evidence, so nothing is captured or
written to the evidence directory. The entry only verifies the evidence config and
the runtime ownership label, so it works from any Devstack checkout. You get
workdir `/edx/app/edxapp/edx-platform` (a copy for a snapshot run, a symlink to the live checkout for a development run), `/edx/app/edxapp/venvs/edxapp/bin` first on `PATH`, the run's
`PY313_*` namespace and secrets (passed to the container by name, never on argv),
`PYTHONPATH=/startup/settings` and `DJANGO_SETTINGS_MODULE=startup_lms|startup_cms`.
Use `python manage.py lms shell` (or `cms`) inside; it needs a TTY on the host.
`run.py --config ... exchange <unique-label>` runs the existing nine-case process
contract with explicit isolated settings; it does not contact a real IdP.

## Image identity

The six infrastructure services are locked to the OCI index digests in
`infrastructure-images.lock.json`. Each record keeps the source tag used for
inspection, the manifest's published version when available, the immutable
index reference, and the amd64/arm64 child-manifest digests. The source tag is
traceability metadata; replay configuration uses the index digest. Valkey's
inspected OCI index exposes no version annotation, so its recorded `8.1` source
tag is not presented as an exact image release.

Registry metadata was checked with `docker buildx imagetools inspect` on
2026-10-27; every index includes `linux/amd64` and `linux/arm64`. `load_config()`
validates the lock schema and rejects mutable service tags or references that
differ from the lock. The audit compares the configured image, container image
reference, and Docker image `RepoDigests`. It normalizes Docker Hub's optional
`docker.io/library/` prefix while requiring the repository and index digest to
match. It also checks that Docker's selected OS/architecture/variant appears in
the locked platform manifest map and records that map's digest for the reported
platform. Docker image inspection does not expose the selected platform
manifest's registry digest directly; the report distinguishes the locked index
and platform-manifest digests from Docker's local image ID. A cached local arm64
image ID is not a substitute for the multi-platform index digest. The runtime image has the
same two forms: a local, architecture-specific `sha256:` image ID, or the multi-platform
reference locked in `runtime-image.lock.json` (OCI index digest plus the amd64/arm64 manifest
digests, built from the `internal-delivery` stage by `docker/py313/build-runtime-image.py`).
For the locked form `preflight`/`create` pull the digest when it is absent (retried with
backoff), reject any other reference, and the audit records the index digest, RepoDigests and
the matching locked platform manifest like the service images.

The audit inspects each of the six service containers and the runtime container,
checks the replay ownership label and configured image reference, then records
the expected and actual configured image references, selected image ID, repository digests, source tag/version, index digest,
matching platform-manifest digest, OS, architecture and variant in
`<label>-selected-images.json`. This records what Docker actually selected; it
does not claim that an integrated replay has run.

`install` records the identity probe's pass output and stores the detailed package
identity report in the evidence directory with mode 600. It does not echo the
report to the terminal because package direct-URL metadata may be sensitive.

After business checks, use `audit_and_collect.py --config ... --label <unique>`.
This checks exact exported/runtime source identity, captures selected inspect and
redacted worker logs, and scans known protected values plus credential patterns.
HTTP authentication logs are not exported. Installed package identities are checked by
Platform's `ci/py313/companion_inputs.py` (`installed-companion-identity.json`) and
`verify-platform-identity.py`, executed in the new runtime.

## Failure and ownership semantics

Output labels are reserved exclusively **before** executing their commands. A
duplicate label cannot repeat an initialization, install, or business mutation.
Every recorded command includes config SHA256, run id, and full source commits.
Runtime commands require a Docker ownership label matching that exact config.
Changing a config cannot retarget an existing evidence tree or container.

There is no resume, delete, down, cleanup, or restart action. A failed phase keeps
its outputs and resources. Diagnose it, then use another explicit label only for
a justified bounded follow-up, or provision a wholly new configuration for a full
replay. Do not remove resources to make a fresh-run check pass.

Test the collision/reservation boundaries with `test_core.py`. These tests use
temporary files and controlled inventories; they do not mutate Docker resources.
Real empty/conflicting target preflight and replay evidence are still required.

See [constant inventory](constant-inventory.md) for migrated and retained values.
