# Explicit local replay

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
| Runtime resources | `runtime_container`, `runtime_volume`, `network`, `lms_port`, `cms_port` |
| Namespace | `database`, `test_database`, `mongo_database`, `cache_prefix`, `es_prefix`, `queue_prefix`, `course_key` |
| Infrastructure | `services`: explicit `container` for mysql/mongo/rabbitmq/elasticsearch/memcached/valkey, plus `volume` for the first four |
| Images | `images`: all six infrastructure services plus runtime; runtime requires `sha256:<64 hex>` |

All resource and namespace names must contain `run_id`. SQL database names start
with `py313_rebuild_` because this is the existing local model-sync initializer.
The course key is a complete opaque `course-v1:` key containing the run id. Ports
are host loopback mappings to the fixed internal LMS/CMS ports 18000/18010.
The export and evidence directories must be new and separate from protected env.

`provision-secrets` creates only six random service secrets in a new protected
file. Namespace values cannot appear in this file and cannot override the JSON
contract. Existing `PY313_*` host environment values are discarded.

## Execution order

With an explicit operator-created JSON config, run `run.py --config ...` with:

1. `provision-secrets` (refuses an existing file).
2. `preflight` (read-only dry check; containers/volumes/networks, ports, paths,
   private mounts, source HEAD and tracked cleanliness).
3. `prepare` (rechecks, creates evidence, exports committed sources only).
4. `create` (rechecks physical resources, creates a new network and fresh service
   data, then a new runtime volume/container).
5. `install` (frozen positive/negative preflight, then empty venv installation).

Then `replay_after_install.py --config ... schema`, `assets`, and `services`.
The schema phase uses fresh local model synchronization, not historical migration.
Actual staff authoring/publication and ordinary learner acceptance remain separate
business steps; these commands do not seed a passing published course.

`run_check.py --config ... lms <unique-label> check` runs a bounded manage command.
It also supports CMS and explicit registered settings such as `startup_schema`.
`run.py --config ... exchange <unique-label>` runs the existing nine-case process
contract with explicit isolated settings; it does not contact a real IdP.

After business checks, use `audit_and_collect.py --config ... --label <unique>`.
This checks exact exported/runtime source identity, captures selected inspect and
redacted worker logs, and scans known protected values plus credential patterns.
HTTP authentication logs are not exported. The installed-source identity probe is
`/startup/replay/verify_installed_identity.py`, executed in the new runtime.

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
