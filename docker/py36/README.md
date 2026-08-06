# Py3.6 Image Build & Run Guide

> Status: HISTORICAL INTERACTIVE BOOTSTRAP
>
> Reproducible Python 3.6 identities are recorded in the
> [integration ledger](https://github.com/Learningtribes/platform/blob/migration_discussion/docs/migration_discussion/13-python36-integration-ledger-20260731.md),
> the branch-qualified
> [integration plan](https://github.com/Learningtribes/platform/blob/py36-integration-r1/docs/plans/py36-integration-probe-plan-20260728.md),
> and
> [runtime evidence](https://github.com/Learningtribes/platform/blob/py36-integration-r1/docs/plans/py36-integration-evidence.md).
> A locked image requires those exact source, dependency, freeze, and runtime
> proofs; this guide preserves the original bootstrap only.

## Build

```bash
cd /Users/noahwang/workspace/hawthorn/devstack/docker/py36
docker build -t ltdps/edxapp:py36 .
```

## Test (interactive)

```bash
docker run --rm -it \
  -v /Users/noahwang/workspace/hawthorn/platform:/edx/app/edxapp/edx-platform \
  --network devstack_default \
  ltdps/edxapp:py36 bash
```

## Verify

```bash
# Bootstrap environment
docker exec <container> bash -c '
  cd /edx/app/edxapp/edx-platform
  pip install -e common/lib/xmodule
  pip install -e common/lib/capa
  pip install -e common/lib/calc
  pip install -e common/lib/symmath
  pip install -e common/lib/safe_lxml
  pip install -e common/lib/chem
  pip install -e common/lib/sandbox-packages
  pip install -e common/lib/dogstats
  pip install -e .
'
```

## Docker Compose (with devstack)

```yaml
# Add to devstack/docker-compose.yml
services:
  lms-py3:
    image: ltdps/edxapp:py36
    volumes:
      - ../platform:/edx/app/edxapp/edx-platform
    networks:
      - devstack_default
    ports:
      - "18001:8000"
    command: python3 manage.py lms runserver 0.0.0.0:8000 --settings=devstack_docker
```

## Notes

- celery 3.1 + kombu 3.0 kept unchanged (async = soft keyword on 3.6)
- mysqlclient 1.4.6 (Juniper bridge version, dual Py2/3 compat)
- pymongo 3.9.0 + mongoengine 0.10.0 (Juniper-verified combo)
- Django 1.11.29 (officially supports Py3.5-3.7)
- Platform source is volume-mounted, not baked into image
- Network must be `devstack_default` to reach MySQL/Mongo
- Shared DB safety: use separate py3 schema for migrations
