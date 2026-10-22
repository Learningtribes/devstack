# Py3.13 local environment

Reference infrastructure (ops versions) plus a `python:3.13-slim-bookworm` runtime image (pinned by digest). Native on the host architecture; no amd64 emulation. Not a production build contract: the pins in `requirements-infra.txt` are probe versions taken from the ops reference table, not frozen choices; `requirements-native-probe.txt` is unpinned. Do not push or open a PR from this branch before the Py3.6 C5 gate.

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
