# Current py3-master isolated replay

Latest bounded result: [2026-11-02 repair and replay](current-replay-20261102.md).
Use its frozen candidate identities when interpreting that evidence; the example
below retains the historical R2 configuration and must be replaced for any new run.

## Quickstart: local LMS and Studio

Prerequisites: Docker with Compose v2 (about 16 GiB and 10 CPUs for the VM), `uv`, `git`, `openssl`,
registry access (the locked runtime image is pulled by digest on first use, with retries), the Platform
checkout at `../platform` (branch `py3-master`, clean tracked tree) and this Devstack checkout with a clean
tracked tree. Python 3.13 is the only supported runtime.

### Development environment (fixed, no arguments)

```sh
make py313-dev-up    # run dev313: LMS :18000, Studio :18010, Platform = ../platform
make lms-shell       # also cms-shell / studio-shell
make py313-restart   # after changing Platform code
make py313-status
make py313-destroy   # removes containers, volumes and network; the run directory stays
```

The Platform checkout is bind-mounted read-write at `/workspace/platform`, and after the install stage
`/edx/app/edxapp/edx-platform` becomes a symlink to it, so the editable installs (Open_edX, xmodule, capa, ...), the
cwd and the settings all see your working tree, not a copy. Install inputs and the installed entry-point
metadata still come from the committed export, so changed `setup.py` entry points or dependencies need a
new environment. Consequences: uncommitted edits take
effect on `make py313-restart` (the servers run with `--noreload`); the asset build writes ignored files
(`node_modules`, `common/static/bundles`, `lms/static/css`, ...) into the checkout; ignored leftovers in the
tree are visible to the runtime (the locale build therefore compiles only git-tracked catalogs).
Theme: the theme is not packaged with Platform or Devstack any more. Every run bind-mounts the `THEME_REPO` checkout
(e.g. `make py313-up ... THEME_REPO=~/workspace/hawthorn/src/themes/hawthorn`, `py313-dev-up` defaults to the sibling
`src/themes/hawthorn`) read-write at `/workspace/themes/hawthorn`; it replaces the former snapshot in `COMPREHENSIVE_THEME_DIRS`. Its content is not
verified against `theme_commit` (recorded only; keep the checkout on the theme repo's `py3-master`). The sites keep using the theme name `hawthorn`, so the checkout must be a `hawthorn`-style theme
(`lms/`, `cms/`, `common/` at its root). Sass output goes to the checkout's git-ignored `lms/static/css` and
`cms/static/css`. After editing theme files, rebuild with `paver update_assets` (compiles themes found in the theme dirs)
or `bash /startup/build_frontend.sh`, then `make py313-restart` if templates are cached. The mount is fixed when the
container is created, so adding or changing `THEME_REPO` needs `make py313-destroy PURGE_DIR=1 && make py313-dev-up`.
Staging servers use the same Platform-owned scripts with `PY313_THEME_SOURCE` / `PY313_THEME_COMMIT` instead of a mount (Platform `ci/py313/bringup/prepare_theme_inputs.py`).
Override `RUN_ID`, `LMS_PORT`, `CMS_PORT` or `PLATFORM_REPO` for another environment, and
`PY313_CONFIG=<run>/config.json` to point the targets below at it. `py313-restart` leaves no evidence.

### Snapshot-platform run (acceptance)

```sh
git -C /path/to/platform worktree add --detach /path/to/platform-worktree origin/py3-master
make py313-up RUN_ID=master313r16 LMS_PORT=18100 CMS_PORT=18110 PLATFORM_REPO=/path/to/platform-worktree
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
- `make lms-shell` (also `cms-shell`, `studio-shell`) and `make py313-status` target the development environment unless `PY313_CONFIG` names another run; status shows container states, ports and heartbeats.
- `make py313-destroy` is an explicit operator teardown, separate from the replay
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

The sections below describe the individual stages that `py313-up` runs.

Use [the exact configuration contract](README.md) and
[current-config.example.json](current-config.example.json). Replace all absolute
host paths, choose a new run ID and replace it in **every** resource/namespace,
then choose unused ports and a non-overlapping RFC1918 /24. Keep both full source
commits fixed; the example Devstack SHA is the executable adapter used for this
attempt, not a claim that every subsequent documentation HEAD was replayed.

Use independent clean Git worktrees. This adapter is based on Devstack
`e19e059cc7091d435dd5121b586da0d525a350c5`; Platform was fetched from py3-master
and frozen at `7dcbcca0651875f0b7748216847715e60f3af706`. Do not copy dirty
checkout changes or historical venvs/data/secrets/assets. Only the complete current
Platform installer is supported here; the former `install_internal_delivery.py`,
`install.sh` and registered-source installers were removed.

## Prerequisites and images

`images.runtime` is either the locked reference `ltdps/edxapp@sha256:<index digest>` from
`runtime-image.lock.json` (multi-platform index; preflight and create pull it by digest when it is not
present, with retries, and the audit records its RepoDigests and platform) or a local `sha256:<64 hex>`
image ID. Any other reference is rejected. The six service references must match
`infrastructure-images.lock.json` exactly. AMD64 execution has not been verified; the locked index
carries an amd64 manifest built under emulation.
Docker/Compose, uv, Git, OpenSSL and package-index/pinned Git access are required.
Check disk, Docker memory, current resource inventory and host LAN/VPN routes first.
Do not free capacity by deleting historical environments.

## Commands

From the committed Devstack worktree, define absolute operator-selected paths:

```sh
REPLAY=docker/py313/probe/startup-20261024-run01/replay
CONFIG=/absolute/new-run/config.json
uv run --no-project --python 3.13 python -B -m unittest discover -s "$REPLAY" -p 'test_*.py' -v
```

`new_run.py` creates the config, the mode-700 `private/` directory and the mode-600 JWT key for
you (`make py313-new-run`). To do it by hand, create a **new** parent directory for the
config/outputs and a new mode-700 private subdirectory, generate a new RSA private key with
`openssl genrsa -out PATH 2048`, chmod it 600 (`PATH` must equal `jwt_file`). Never print or commit
secrets. `bring_up.py --config "$CONFIG"` runs everything below plus the post-install stages. Run
the stages individually, stopping at any nonzero exit:

```sh
uv run --no-project --python 3.13 python -B "$REPLAY/run.py" --config "$CONFIG" provision-secrets
uv run --no-project --python 3.13 python -B "$REPLAY/run.py" --config "$CONFIG" provision-acceptance
uv run --no-project --python 3.13 python -B "$REPLAY/run.py" --config "$CONFIG" preflight
uv run --no-project --python 3.13 python -B "$REPLAY/run.py" --config "$CONFIG" prepare
uv run --no-project --python 3.13 python -B "$REPLAY/run.py" --config "$CONFIG" create
uv run --no-project --python 3.13 python -B "$REPLAY/run.py" --config "$CONFIG" install
uv run --no-project --python 3.13 python -B "$REPLAY/replay_after_install.py" --config "$CONFIG" schema
uv run --no-project --python 3.13 python -B "$REPLAY/replay_after_install.py" --config "$CONFIG" assets
uv run --no-project --python 3.13 python -B "$REPLAY/replay_after_install.py" --config "$CONFIG" services
```

The original schema initializer synchronizes models in a fresh synthetic database;
it does not replay historical migrations. Asset execution is real npm-ci,
XModule/theme/static compilation, webpack for both systems, locale and collectstatic.
Service dispatch alone is not readiness: inspect run-owned HTTP/worker logs, loopback
responses and owned queue routing. Follow the browser/task/persistence checks in
the main replay README and capture the audit only after those prerequisites pass.
Never expose private authentication HTTP logs as evidence.

## Interactive shell

```sh
make lms-shell    # DJANGO_SETTINGS_MODULE=startup_lms
make cms-shell    # DJANGO_SETTINGS_MODULE=startup_cms (make studio-shell is an alias)
```

Run from the Devstack worktree on a host terminal. With no arguments the target is the development
environment (`$PY313_RUNS_ROOT/dev313/config.json`); set `PY313_CONFIG` for another run. The shell starts
in `/edx/app/edxapp/edx-platform` (a copy for a snapshot run, the live checkout for a development run) inside the run-owned runtime with `/edx/app/edxapp/venvs/edxapp/bin` first on `PATH` and the run's namespace
and secrets in the environment, so `python manage.py lms shell` works directly. It is not an
evidence-capturing command (no label, nothing recorded); use `run_check.py` for
reproducible output.

From the shell, `paver test_system -s lms|cms -C --fasttest` and `paver update_assets` work as is. The shell exports
`PAVER_DEVSTACK_SETTINGS=devstack_local`, Paver's default settings for this runtime: Platform's `lms.envs.devstack_local` /
`cms.envs.devstack_local` import the runtime's `startup_lms` / `startup_cms`. Paver's classic default (`devstack`) imports
`lms.envs.aws`, which needs production config (`CELERY_RESULT_BACKEND`, `lms.env.json`, `lms.auth.json`) this runtime
does not have. `paver update_assets` therefore builds into `/edx/app/edxapp/py313/static`, which the running servers use. It needs
Platform with `devstack_local` (Platform PR "devstack_local settings and PAVER_DEVSTACK_SETTINGS"). `lms-watcher-shell` and `studio-watcher-shell` still target the
classic Python 2.7 containers.

No resume/reset/cleanup/restart fallback is provided. Output labels are exclusive,
so a failure preserves evidence and cannot silently repeat a mutation. After an
executable adapter change, commit it and use a new run config/export/resources.
Application failures end dependent stages; record a focused follow-up instead of
patching installed sources or weakening checks. This is local development acceptance,
not old-data upgrade, external provider acceptance, production rollout or CI cutover.
