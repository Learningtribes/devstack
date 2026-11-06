# Py3.13 local environment

## Quickstart: local LMS and Studio

Prerequisites: Docker with Compose v2 (about 16 GiB and 10 CPUs for the VM), `uv`, `git`, `openssl`,
registry access (the locked runtime image is pulled by digest on first use, with retries), a clean
Platform `py3-master` worktree and this Devstack checkout with a clean tracked tree.

```sh
git -C /path/to/platform worktree add --detach /path/to/platform-worktree origin/py3-master
make py313-up RUN_ID=master313r16 LMS_PORT=18000 CMS_PORT=18010 PLATFORM_REPO=/path/to/platform-worktree
```

`py313-up` runs `new_run.py` (run directory under `$PY313_RUNS_ROOT`, default
`~/workspace/hawthorn/py313-runs/<RUN_ID>`; private inputs in `private/` mode 700; first free
`172.30.X.0/24`) and then `bring_up.py`: unit tests, secrets, preflight, export, create, install,
schema, assets, services, heartbeats, course build and seed, superuser, HTTP smoke. It stops at the
first failing stage; per-stage logs and durations are in `<run>/stage-logs/`, the outcome in
`<run>/bring-up-result.json`. Optional variables: `PLATFORM_COMMIT`, `DEVSTACK_REPO`,
`DEVSTACK_COMMIT` (default: each checkout's HEAD), `RUN_ROOT`, `SUBNET`, `RUNTIME_IMAGE`,
`SKIP_UNIT_TESTS=1`.

- URLs: LMS `http://localhost:<LMS_PORT>`, Studio `http://localhost:<CMS_PORT>`.
- Superuser (local devstack only, not a secret): `edx` / `edx@example.com` / `edx`. Override with
  `PY313_DEV_SUPERUSER_USERNAME`, `PY313_DEV_SUPERUSER_EMAIL`, `PY313_DEV_SUPERUSER_PASSWORD`
  in the host environment.
- Run-scoped acceptance identities (staff, learner, ...): `<run>/private/acceptance.json`, mode 600.
- `make lms-shell PY313_CONFIG=<run>/config.json` (also `cms-shell`, `studio-shell`).
- `make py313-status PY313_CONFIG=...` shows container states, ports and heartbeats.
- `make py313-destroy PY313_CONFIG=...` is an explicit operator teardown, separate from the replay
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
`make studio-shell`) open a shell in its runtime; `PY313_CONFIG=/absolute/path/to/config.json` is required.


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
