# Py3.13 local environment

Reference infrastructure (ops versions) plus a `python:3.13-slim-bookworm` runtime image. Native on the host architecture; no amd64 emulation. Not a production build contract: pins in `requirements-infra.txt` are the ops reference versions, `requirements-native-probe.txt` is unpinned.

```bash
cd docker/py313
make env      # writes .env with random passwords (mode 600, git-ignored)
make up       # MySQL 8.4, MongoDB 8.0, RabbitMQ 4.3, Memcached 1.6, Valkey 8.1, Elasticsearch 8.19
make build    # ltdps/edxapp:py313-local (Debian/PyPI mirrors are build args, defaults in Makefile)
make smoke    # client-to-service checks from inside the image
make shell    # bash with $(PLATFORM_DIR) mounted at /edx/app/edxapp/edx-platform
make destroy  # stop and delete volumes
```

Host ports (127.0.0.1 only): MySQL 13306, MongoDB 27117, RabbitMQ 15673 (management 15674), Memcached 11311, Valkey 16379, Elasticsearch 19200.

RabbitMQ 4.3 denies non-exclusive transient queues by default; `rabbitmq/20-permit-transient-nonexcl.conf` re-enables them for Celery's pidbox queues.
