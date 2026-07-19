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

**Key decision: share data services where possible.** Py3 cannot complete `provision`, and sharing the existing validated data makes it easier to distinguish Py3 code bugs from data/config issues.

| Resource | Strategy | Reason |
|----------|----------|--------|
| Containers | Different project name (`py3devstack`) | No name conflicts |
| Ports | +100 offset (18100/18110/...) | No port conflicts |
| MySQL | **Shared** — same `edxapp` database, read-write | mysqlclient 1.4.6 supports both Py2 & Py3 on MySQL 5.6 |
| MongoDB | **Shared** — same `edxapp` database | pymongo 3.12 works with MongoDB 2.6–5.0 |
| Elasticsearch | **Shared** — same indices | elasticsearch-py 1.9.0 is pure Python; optional `*_py3` alias if mapping needs diverge |
| Memcached | **Separate** instance (port 11212) | **Pickle format incompatible Py2↔Py3** — MUST isolate |
| Source code | Shared mount (read-only from Py3 side) | Edits on Py2; Py3 sees same code |
| Devpi | Shared (read-only) | pip cache agnostic |

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
# Py3 only needs its own memcached — MySQL/Mongo/ES/devpi are shared
cd /Users/noahwang/workspace/hawthorn/devstack
```

### 4.2 Docker Compose Override

Py3 environment only needs LMS + Studio + Discovery + its own memcached. Data services (MySQL/Mongo/ES/Devpi) are shared from the Py2 environment.

```yaml
# docker-compose-py3.yml
version: '2.1'

services:
  memcached:
    ports:
      - "11212:11211"

  lms:
    image: ltdps/edxapp:latest  # eventually py3-dev image
    ports:
      - "18100:18000"
    platform: linux/amd64

  studio:
    image: ltdps/edxapp:latest
    ports:
      - "18110:18010"
    platform: linux/amd64

  discovery:
    image: ltdps/discovery:latest
    ports:
      - "18382:18381"
    platform: linux/amd64
```

### 4.3 Start Py3 Environment

```bash
# Py2 (unchanged) — runs MySQL/Mongo/ES/Memcached/Devpi
DEVSTACK_WORKSPACE=$HOME/workspace/hawthorn \
  docker compose -f docker-compose.yml -f docker-compose-host.yml up -d

# Py3 (only app containers + its own memcached)
COMPOSE_PROJECT_NAME=py3devstack \
  DEVSTACK_WORKSPACE=$HOME/workspace/hawthorn \
  docker compose -f docker-compose.yml -f docker-compose-py3.yml up -d lms studio discovery memcached

# Verify
docker compose ps                              # Py2: 10 containers
COMPOSE_PROJECT_NAME=py3devstack docker compose ps  # Py3: 3 containers

---

## 5. Caveats — Shared Data Risks

When Py3 pip library upgrades could break old-database compatibility:

| Upgrade | Risk to Shared Data | Mitigation |
|---------|:-------------------:|------------|
| mysqlclient 2.x | Drops Py2 support, may need MySQL features 5.6 doesn't have | **Stay on 1.4.6** until both Py2 dropped AND MySQL upgraded |
| pymongo 4.x | Requires MongoDB ≥3.6 | **Stay on 3.12** until MongoDB upgraded (independent track) |
| elasticsearch-py 7.x | Requires ES ≥6.x | **Stay on 1.9.x** until ES replaced |
| Django ORM migration | Schema changes write to shared DB | Run migrations on Py2 first; Py3 reads same schema |
| Session serialization | Py2 sessions in DB may not deserialize in Py3 | Use `SESSION_SERIALIZER='django.contrib.sessions.serializers.JSONSerializer'` (already set) |

**Rule: any upgrade that changes database schema or wire protocol must first be verified against the existing Py2 data.**

---

## 6. Testing Workflow

### 6.1 Run a Single Test in Py3

```bash
COMPOSE_PROJECT_NAME=py3devstack \
  docker exec -it py3devstack-lms-1 bash -c '
    source /edx/app/edxapp/edxapp_env &&
    cd /edx/app/edxapp/edx-platform &&
    python -m pytest common/djangoapps/student/tests/test_login.py \
      --ds=cms.envs.test
  '
```

### 6.2 Compare Py2 vs Py3

```bash
# Py2
docker exec edx.devstack.lms python -m pytest path/to/test.py > /tmp/py2.out

# Py3
COMPOSE_PROJECT_NAME=py3devstack \
  docker exec py3devstack-lms-1 python -m pytest path/to/test.py > /tmp/py3.out

diff /tmp/py2.out /tmp/py3.out
```

---

## 7. Risk Items

| Item | Risk | Mitigation |
|------|:----:|------------|
| Django 1.11 on Py3.8 (unofficial) | 🟡 | Spy smoke-test first; be ready to target Py3.7 |
| Celery 3.1→4.4 API changes | 🔴 | Test on Py2 first; update all `@task` decorators |
| Memcached pickle cross-Py | 🔴 | Separate memcached instance; use KEY_PREFIX |
| Shared source mount edits | 🟡 | Use separate worktree or mount read-only for Py3 |
| LT-fork XBlock Py3 compat | 🔴 | Test each XBlock individually; may need upstream forks |
| pymongo 3.12 API changes | 🟡 | `count()` → `count_documents()` etc. |

---

## 8. When to Create the Py3 Environment

| Milestone | Action |
|-----------|--------|
| Now | Create `docker-compose-py3.yml`, document strategy |
| Phase A (driver bridge) | Test on Py2 only; no Py3 env needed |
| Phase B (celery) | Test on Py2 first; spin up Py3 env after Py2 passes |
| Phase C (Django+Py3.8) | Py3 env required; full data separation |
| Phase D (XBlock) | Py3 env used for per-XBlock isolation tests |
