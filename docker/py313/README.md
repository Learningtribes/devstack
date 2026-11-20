# Py3.13 local environment

## Quickstart: local LMS and Studio

Prerequisites: Docker with Compose v2 (about 16 GiB and 10 CPUs for the VM), `uv`, `git`, `openssl`,
registry access (the locked runtime image is pulled by digest on first use, with retries), a clean
Platform `py3-master` worktree and this Devstack checkout with a clean tracked tree.

```sh
git -C /path/to/platform worktree add --detach /path/to/platform-worktree origin/py3-master
make py313-up RUN_ID=master313r16 LMS_PORT=18000 CMS_PORT=18010 PLATFORM_REPO=/path/to/platform-worktree
```

`py313-up` runs `new_run.py` (run directory under `$BRINGUP_RUNS_ROOT`, default
`~/workspace/hawthorn/py313-runs/<RUN_ID>`; private inputs in `private/` mode 700; first free
`172.30.X.0/24`) and then `bring_up.py`: unit tests, secrets, preflight, export, create, install,
schema, assets, services, heartbeats, course build and seed, superuser, HTTP smoke. It stops at the
first failing stage; per-stage logs and durations are in `<run>/stage-logs/`, the outcome in
`<run>/bring-up-result.json`. Optional variables: `PLATFORM_COMMIT`, `DEVSTACK_REPO`,
`DEVSTACK_COMMIT` (default: each checkout's HEAD), `RUN_ROOT`, `SUBNET`, `RUNTIME_IMAGE`,
`SKIP_UNIT_TESTS=1`.

- URLs: LMS `http://localhost:<LMS_PORT>`, Studio `http://localhost:<CMS_PORT>`.
- Superuser (local devstack only, not a secret): `edx` / `edx@example.com` / `edx`. Override with
  `BRINGUP_DEV_SUPERUSER_USERNAME`, `BRINGUP_DEV_SUPERUSER_EMAIL`, `BRINGUP_DEV_SUPERUSER_PASSWORD`
  in the host environment.
- Run-scoped acceptance identities (staff, learner, ...): `<run>/private/acceptance.json`, mode 600.
- `make lms-shell BRINGUP_CONFIG=<run>/config.json` (also `cms-shell`, `studio-shell`).
- `make py313-status BRINGUP_CONFIG=...` shows container states, ports and heartbeats.
- `make py313-destroy BRINGUP_CONFIG=...` is an explicit operator teardown, separate from the replay
  stages (which never clean up): it removes only the containers, volumes and network named in that
  config that carry its `py313.replay.config` ownership label, and keeps the run directory
  (`PURGE_DIR=1` deletes the run's known outputs, `DRY_RUN=1` only reports).

### Runtime image maintenance

The runtime base is the `internal-delivery` stage of `docker/py313/Dockerfile`, published as the
multi-platform (linux/amd64 + linux/arm64) image `ltdps/edxapp:py313-devstack-YYYYMMDD` and locked in
`replay/runtime-image.lock.json` (tag, index digest, per-platform manifest digests, source commit).
Replay configs use `images.runtime = ltdps/edxapp@sha256:<index digest>`; a local `sha256:` image ID
is still accepted. To publish a new image, commit the change, then from a clean tree:

```sh
uv run --no-project --python 3.13 python -B docker/py313/build-runtime-image.py \
  --tag ltdps/edxapp:py313-devstack-YYYYMMDD --context /new/dir
```

The script refuses `latest`/implicit tags, an existing remote tag and a dirty tree, builds from
`git archive HEAD`, pushes with `docker buildx build --push`, reads the pushed index and writes the
lock. Commit the lock in a follow-up commit and update `images.runtime` in
`replay/current-config.example.json`. `--lock-only --source-commit SHA` records an already pushed tag,
`--registry-proxy URL` routes the client-side registry reads through a proxy (polluted DNS), and
`--build-arg` accepts the Debian/PyPI/Node mirror settings.

For current py3-master complete installation and isolated deployment, use the
[explicit replay](probe/startup-20261024-run01/replay/README.md). It consumes the
Platform application/Paver/test locks, the Platform-pinned external sources
(git SHA pins and +hawthorn.1 companions) and ten editables. The older shell/probe commands below are historical
infrastructure tools and do not install that contract.
Once a replay is running, the root `make lms-shell` / `make cms-shell` (alias
`make studio-shell`) open a shell in its runtime; `BRINGUP_CONFIG=/absolute/path/to/config.json` is required.


Reference infrastructure (ops versions) plus a `python:3.13-slim-bookworm` runtime image (pinned by digest). Native on the host architecture; no amd64 emulation. Not a production build contract: the pins in `requirements-infra.txt` are probe versions taken from the ops reference table, not frozen choices; `requirements-native-probe.txt` is unpinned.

```bash
cd docker/py313
make env      # appends missing random passwords to .env (mode 600, git-ignored)
make up       # MySQL 8.4, MongoDB 8.0 (auth on), RabbitMQ 4.3, Memcached 1.6, Valkey 8.1, Elasticsearch 8.19
make build    # runtime image (smoke) and dev image (compiler toolchain); Debian/PyPI mirrors are build args
make smoke    # client-to-service checks with assertions; uses a throwaway MySQL database and cleans up
make rmq-matrix  # Celery 5.6 pidbox matrix against a default-policy RabbitMQ 4.3 control broker
make shell PLATFORM_DIR=/path/to/platform-worktree
make venv-reset  # drop the named venv volume used by `make shell`
make destroy  # stop and delete volumes
```

`make shell` refuses a main checkout (use `git worktree add`; override with `ALLOW_MAIN_CHECKOUT=1`) and mounts `/opt/venv` from the named volume `py313_venv`, so packages installed there survive `--rm`. The volume is seeded from the dev image on first use; run `make venv-reset` after rebuilding the image. `PIP_INDEX_URL` is passed at run time, not baked into the image.

Entering the environment (run `make` on the host, not inside a container):

```bash
# plain Python 3.13, no platform code, packages are lost on exit
docker run --rm -it --network py313_default --env-file .env ltdps/edxapp:py313-local bash
# dev shell with a platform worktree and a persistent venv
make shell PLATFORM_DIR=/path/to/platform-worktree
```

Service hostnames inside the network are `mysql`, `mongo`, `rabbitmq`, `memcached`, `valkey`, `elasticsearch`; credentials come from `.env` via `--env-file`.

Host ports (127.0.0.1 only): MySQL 13306, MongoDB 27117, RabbitMQ 15673 (management 15674), Memcached 11311, Valkey 16379, Elasticsearch 19200.

RabbitMQ 4.3 denies non-exclusive transient queues by default; `rabbitmq/20-permit-transient-nonexcl.conf` re-enables them for Celery's pidbox queues. The `noperm` compose profile starts a default-policy broker for the control experiment.

## Optional: course-discovery sidecar

`mode: "py313, optional"`. A run with `discovery_repo` also gets one course-discovery
container on the same network. It reuses that run's MySQL (its own database) and memcached,
so enabling it costs one container and no extra infrastructure. Runs created without
`discovery_repo` keep their config hash and are unaffected.

```sh
make py313-build-discovery DISCOVERY_REPO=/path/to/discovery
make py313-dev-up ... DISCOVERY_REPO=/path/to/discovery \
  DISCOVERY_IMAGE=ltdps/discovery:py313-local DISCOVERY_PORT=18381
```

`py313-dev-up` builds a **missing tag** itself, from `DISCOVERY_REPO`, so the explicit
`py313-build-discovery` above is only needed when it is absent from this checkout, or to rebuild
on purpose. A `DISCOVERY_IMAGE` given as `repo@sha256:<digest>` is never built: it is a published
reference, pulled by `preflight` like the platform runtime image. `py313-up`, the canonical
non-development path, never builds — it fails instead, naming the command to run.

`py313-start` / `py313-stop` / `py313-restart` / `py313-destroy` cover discovery
automatically: `lifecycle.py` enumerates it when the config carries `discovery_repo`. The
discovery-only commands are `py313-shell-discovery`, `py313-status-discovery` (exits non-zero
unless the container runs and `/health/` returns 200) and `py313-update-db-discovery`.

### Two halves of the contract, and neither is optional

Discovery only reads courses when both of these exist:

| Row | Written by | Why it is needed |
| --- | --- | --- |
| `oauth2_provider.Application` (LMS database) | Platform `ci/py313/bringup/seed_discovery_oauth_app.py`, run during the `schema` stage | Discovery authenticates to the LMS with the OAuth2 client-credentials grant |
| `django_site` + `core_partner` (discovery database) | `discovery.py seed()` -> discovery's `ci/py313/seed_sites_and_partners.py` | `refresh_course_metadata` raises `CommandError` on an empty `django_site`; `core_partner` is the org-ownership backbone |

The DOT credentials are derived per run from that run's startup secret
(`core.discovery_oidc_credentials`) rather than stored in the config: they stay unique per
run, never appear in a committed file, and adding them would otherwise change the config
hash of every run created before discovery existed. `seed()` writes the **in-network** LMS
address (`<run>-runtime:18000`) as `django_site.domain`, because discovery runs in a
different container than the LMS; the host loopback port is unusable there.

### Merge order with course-discovery

The discovery half of this contract is split across two repositories, and the two halves are
only consistent together:

| Change | Lives in |
| --- | --- |
| `settings.py313` raises unless `DISCOVERY_LOCAL_RUN=1` | discovery |
| `core.discovery_environment()` writes `DISCOVERY_LOCAL_RUN=1` | this repository |
| Lock paths carry `@COMPANIONS_DIR@`; `materialize-lock.py` resolves them | discovery |
| `discovery.py install()` invokes the materializer and then runs `uv pip sync` | this repository |

Neither side is safe on its own, so the order is a preference rather than a guarantee: merge
them together, and do not run a bring-up between the two merges.

* This repository alone: `install()` runs `<discovery>/ci/py313/materialize-lock.py`, which the
  un-merged discovery checkout does not have, so the discovery `install` stage fails on a
  missing file.
* Discovery alone: `settings.py313` refuses to import until something exports
  `DISCOVERY_LOCAL_RUN`, and its lock names `@COMPANIONS_DIR@`, which the un-merged replay
  passes straight to `pip`. The `check` and `install` stages both fail.
* Discovery first, then this repository: the same two failures, in the same stages, for the
  length of the window. The only reason to prefer it is that a discovery change on its own
  never breaks a non-discovery deployment.

### Local-only trust shortcuts

Discovery verifies the LMS's HS256 JWTs with the run's startup secret and connects to MySQL as the
run's `edxapp` user. Both keep a local run to one container and one secret set; neither belongs in a
shared or long-lived environment, which should use its own signing key and a dedicated database user.

### Token type

The platform LMS resolves a `Bearer` token by `sha256(token)` against
`oauth2_provider.AccessToken.token_checksum`. The opaque token from a `token_type=Bearer`
request therefore authenticates, while the JWT from `token_type=JWT` is rejected with
`token_nonexistent`. Discovery's `course_discovery/settings/py313.py` sets
`COURSES_API['TOKEN_TYPE'] = 'Bearer'`; the management-command default stays `JWT`, so no
other deployment changes behaviour.

### Why discovery's release script is not in this repository

`py313-build-discovery` builds the image locally from `DISCOVERY_REPO`. Publishing a
*released* digest works the same way as for the platform image, but the script lives in the
discovery checkout:

```sh
cd <discovery>
uv run --no-project --python 3.13 python -B ci/py313/build-runtime-image.py \
  --tag ltdps/discovery:py313-devstack-YYYYMMDD --context /new/dir
```

Then set `DISCOVERY_IMAGE=ltdps/discovery@sha256:<index digest>` on the run. The script is
function-for-function comparable with `docker/py313/build-runtime-image.py` here, with two
deliberate differences: its stage is `final` (the last stage of discovery's Dockerfile), and
its lock records `source_commit` rather than `devstack_commit` because the image is built from
the discovery repository.

It stays in the discovery repository because every builder here archives its own tree
(`git archive HEAD`) and builds the Dockerfile beside it: this one archives Devstack and builds
`docker/py313/Dockerfile`, `platform/ci/py313/build-app-image.py` archives Platform and builds
`ci/py313/Dockerfile.app`, and discovery's archives discovery and builds `ci/py313/Dockerfile`.
Moving it here would mean archiving a different repository from the one the script lives in,
which breaks the clean-tree guarantee that makes the build reproducible, and would make a
discovery release depend on a Devstack checkout.
