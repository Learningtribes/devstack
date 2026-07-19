# Python 3 Migration — Devstack Strategy

> Date: 2026-07-19  
> Reference: `platform-migration_discussion/docs/migration_discussion/03-runtime-environment.md`

---

## 1. Core Principle

The existing Py2 devstack must remain intact and working. Py3 testing runs in a **parallel environment** using Docker Compose project isolation.

```
Py2 (prod-equivalent)          Py3 (migration target)
─────────────────────          ─────────────────────
Project: devstack              Project: py3devstack
Ports:   18000/18010/...       Ports:   18100/18110/...
DB:      edxapp (MySQL)        DB:      edxapp_py3 (MySQL)
ES:      courseware_index      ES:      courseware_index_py3
Volumes: devstack_*            Volumes: py3devstack_*
```

---

## 2. Isolation Strategy

| Resource | Strategy | Reason |
|----------|----------|--------|
| Containers | Different project name (`py3devstack`) | No name conflicts |
| Ports | +100 offset (18100/18110/...) | No port conflicts |
| MySQL | Separate database (`edxapp_py3`) | Py3 migrations incompatible with Py2 |
| MongoDB | Shared or separate (`edxapp_py3`) | pymongo bridge compatible both ways |
| Elasticsearch | Separate indices (`*_py3`) | Mapping may diverge |
| Memcached | Separate instance | Pickle format incompatible Py2↔Py3 |
| Source code | Shared mount OR separate worktree | Mount read-only for Py3; edits done on Py2 side |
| Devpi | Shared (read-only) | pip cache is py-version-agnostic |

---

## 3. Migration Phases & Required Environment Changes

### Phase A — Driver Bridge (Batch 1)

Change: pymongo 3.12 / mysqlclient 1.4.6 / python-memcached 1.59

**Testing:** Run on existing Py2 devstack FIRST. These are Py2/3 dual-compatible.
No separate Py3 environment needed yet. Full LMS regression.

### Phase B — Celery Upgrade (celery 3.1 → 4.4)

Change: celery + kombu + django-celery-beat/results

**Testing:** Run on existing Py2 devstack FIRST. Then start Py3 env with upgraded packages.

### Phase C — Django 1.11.29 + Py3.8 Smoke

**Here the Py3 environment becomes essential.**

Change: Switch runtime to Python 3.8, all pip packages rebuilt.

**Testing:** New Py3 container + separated data services.

### Phase D — XBlock Py3 Assessment

Each LT-fork XBlock tested in isolation in Py3 container.

---

## 4. Setup Plan

### 4.1 Prerequisites

```bash
# Separate database
docker exec -i edx.devstack.mysql mysql -uroot -e "CREATE DATABASE IF NOT EXISTS edxapp_py3"

# Project-specific compose
cd /Users/noahwang/workspace/hawthorn/devstack
```

### 4.2 Docker Compose Override

Create `docker-compose-py3.yml` that overrides key settings:

```yaml
version: '2.1'

services:
  mysql:
    environment:
      MYSQL_DATABASE: edxapp_py3
    ports:
      - "13306:3306"

  mongo:
    ports:
      - "27018:27017"

  elasticsearch:
    ports:
      - "19200:9200"

  memcached:
    ports:
      - "11212:11211"

  lms:
    image: ltdps/edxapp:py3-dev  # future Py3 image
    ports:
      - "18100:18000"
    environment:
      EDXAPP_MYSQL_DB_NAME: edxapp_py3

  studio:
    image: ltdps/edxapp:py3-dev
    ports:
      - "18110:18010"
    environment:
      EDXAPP_MYSQL_DB_NAME: edxapp_py3

  discovery:
    image: ltdps/discovery:py3-dev
    ports:
      - "18382:18381"
```

### 4.3 Start Py3 Environment

```bash
# Py2 (unchanged)
DEVSTACK_WORKSPACE=$HOME/workspace/hawthorn \
  docker compose -f docker-compose.yml -f docker-compose-host.yml up -d

# Py3 (separate project)
COMPOSE_PROJECT_NAME=py3devstack \
  DEVSTACK_WORKSPACE=$HOME/workspace/hawthorn \
  docker compose -f docker-compose.yml -f docker-compose-host.yml -f docker-compose-py3.yml up -d

# Verify isolation
docker compose ps                    # 10 containers, ports 18000+
COMPOSE_PROJECT_NAME=py3devstack \
  docker compose ps                   # 10 containers, ports 18100+
```

---

## 5. Testing Workflow

### 5.1 Run a Single Test in Py3

```bash
COMPOSE_PROJECT_NAME=py3devstack \
  docker exec -it py3devstack-lms-1 bash -c '
    source /edx/app/edxapp/edxapp_env &&
    cd /edx/app/edxapp/edx-platform &&
    python -m pytest common/djangoapps/student/tests/test_login.py \
      --ds=cms.envs.test
  '
```

### 5.2 Compare Py2 vs Py3

```bash
# Py2
docker exec edx.devstack.lms python -m pytest path/to/test.py > /tmp/py2.out

# Py3
COMPOSE_PROJECT_NAME=py3devstack \
  docker exec py3devstack-lms-1 python -m pytest path/to/test.py > /tmp/py3.out

diff /tmp/py2.out /tmp/py3.out
```

---

## 6. Risk Items

| Item | Risk | Mitigation |
|------|:----:|------------|
| Django 1.11 on Py3.8 (unofficial) | 🟡 | Spy smoke-test first; be ready to target Py3.7 |
| Celery 3.1→4.4 API changes | 🔴 | Test on Py2 first; update all `@task` decorators |
| Memcached pickle cross-Py | 🔴 | Separate memcached instance; use KEY_PREFIX |
| Shared source mount edits | 🟡 | Use separate worktree or mount read-only for Py3 |
| LT-fork XBlock Py3 compat | 🔴 | Test each XBlock individually; may need upstream forks |
| pymongo 3.12 API changes | 🟡 | `count()` → `count_documents()` etc. |

---

## 7. When to Create the Py3 Environment

| Milestone | Action |
|-----------|--------|
| Now | Create `docker-compose-py3.yml`, document strategy |
| Phase A (driver bridge) | Test on Py2 only; no Py3 env needed |
| Phase B (celery) | Test on Py2 first; spin up Py3 env after Py2 passes |
| Phase C (Django+Py3.8) | Py3 env required; full data separation |
| Phase D (XBlock) | Py3 env used for per-XBlock isolation tests |
