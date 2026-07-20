# Python 3 Migration — Devstack Environment Strategy

> Date: 2026-07-19 (capability boundaries corrected 2026-07-20)  
> Reference: `platform/.claude/skills/python3-migration/` + `CLAUDE.md § Python 3.8 Testing`  
> **⚠️ Corrected:** The migration project already defines a Py3 testing strategy — a lightweight test container, NOT a parallel devstack. This document replaces the earlier original-design speculation with the established project approach.

> ## ⛔ Capability Boundary (read first)
>
> The Py3.8 container is for **syntax + narrow unit verification of already-migrated code**, NOT full LMS/CMS boot under Py3.
>
> - The container installs a **curated** requirements subset (`docs/py38-migration/development.py38.step47.skip-native.txt`), not the full Py2 stack. The full stack does **not** install on Py3.8 (celery 3.1 / kombu 3.0 `kombu.async` = SyntaxError, `MySQL-python`, `pymongo 2.9`).
> - Therefore **`paver test_system -s lms/cms` cannot boot under Py3.8 today.** Full-app Py3 testing only becomes possible after the celery 4.4 + driver Batch-1 bridge lands (see `../../platform-migration_discussion/docs/migration_discussion/03-runtime-environment.md` §5 and `04-infrastructure-dependencies.md` §2).
> - What works **now**: `compileall` syntax checks, and `paver test_lib -C --fasttest` for pure-Python libs / already-migrated modules.
> - These tests DO require a live MySQL (and MongoDB for `ModuleStoreTestCase`) — the test runner creates a `test_*` DB but needs a running server. That is the real reason for `--network host` (reuse the devstack DB services).

---

## 1. Established Strategy (from CLAUDE.md + python3-migration skill)

The migration project uses a minimal Python 3.8 Docker container for targeted test runs. It does NOT attempt to run a full LMS/Studio devstack under Py3.

### Architecture

```
Host (macOS)
├── Devstack (Py2)              Python 3.8 Test Container
│   ├── MySQL :3306             ├── docker run --network host
│   ├── MongoDB :27017          ├── -v "$PWD:/work" (source mount)
│   ├── ES :9200                ├── python:3.8-bullseye
│   └── LMS/Studio :18000/10    ├── /work/.venv (persisted on host)
│                                └── paver test_system -t <module>
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Network host mode** (`--network host`) | **Required** — the test runner needs a live MySQL (+ MongoDB for `ModuleStoreTestCase`); it reuses the devstack DB servers |
| **Source bind-mount** | Code changes visible instantly; no rebuild |
| **`.venv` on host** | Persists across container restarts; no repeated pip install |
| **Curated requirements** | Installs `development.py38.step47.skip-native.txt`, not the full Py2 stack (which won't install on Py3.8) |
| **Separate test DBs** | Runner creates/destroys `test_*` databases on the shared MySQL — no conflict with the Py2 devstack's business data, but the **server must be running** |

### Why NOT a Parallel Devstack

1. Py3 provisioning is not feasible (same reason Py2 provisioning is manual)
2. Test runner creates its own databases — doesn't need a running LMS/Studio
3. The goal is per-module syntax+test verification, not full app functionality
4. Keeping it lightweight avoids hours of setup per session

---

## 2. Setup

### 2.1 Build the Test Container

```bash
cd /Users/noahwang/workspace/hawthorn/platform

# Start container (one-time)
docker run -it --network host \
  --name py38-tool-container \
  --platform linux/amd64 \
  -v "$PWD:/work" \
  -w /work \
  python:3.8-bullseye /bin/bash

# Inside container: one-shot setup (creates /work/.venv)
./.claude/skills/python3-migration/scripts/setup-py38-container.sh
```

After setup, exit the container. `.venv` is persisted at `/work/.venv` on host.

### 2.2 Quick Start

```bash
# Re-enter container
docker start -ai py38-tool-container

# OR fresh container (reuses existing .venv):
docker run -it --network host --platform linux/amd64 \
  -v "$PWD:/work" -w /work \
  python:3.8-bullseye /bin/bash

# Activate and test
source /work/.venv/bin/activate
SKIP_NPM_INSTALL=True paver test_lib -C --fasttest
```

---

## 3. Testing Workflow

### 3.1 Syntax Verification (works now — primary)

```bash
# Inside container
cd /work && source .venv/bin/activate

# Verify a module compiles under Py3 (exclude migrations)
python -m compileall -q lms/djangoapps/<module>/
find lms/djangoapps/<module> -name "*.py" ! -path "*/migrations/*" \
  -exec python -m py_compile {} \;
```

### 3.2 Unit Test — libs / already-migrated modules (works now)

```bash
# Pure-Python libs (xmodule, capa, calc, …) — the primary Py3 unit-test path
SKIP_NPM_INSTALL=True paver test_lib -C --fasttest

# Narrow test_system target: ONLY reliable for already-migrated modules whose
# import chain is Py3-clean. Requires the devstack MySQL/Mongo running.
paver test_system -s lms -t lms/djangoapps/grades/tests/test_models.py \
  --disable-migrations --fail-fast
```

### 3.3 Full Suite — ⛔ BLOCKED under Py3.8 today

`paver test_system -s lms/cms` cannot boot under Py3.8 until the celery 4.4 +
driver Batch-1 bridge lands (see Capability Boundary above). Until then, run the
full LMS/CMS suite in the **Py2 devstack**, and use the Py3 container only for
`compileall` + `test_lib` + narrow already-migrated `test_system` targets.

```bash
# Py2 devstack (full suite) — the current source of truth for LMS/CMS behavior
docker exec edx.devstack.lms bash -c \
  'source /edx/app/edxapp/edxapp_env && cd /edx/app/edxapp/edx-platform && \
   SKIP_NPM_INSTALL=True paver test_system -s lms'

# Py3 container (post-bridge only — expected to fail-to-boot before then)
# SKIP_NPM_INSTALL=True paver test_system -s lms
```

---

## 4. Comparison: Test Container vs Parallel Devstack

| Aspect | Py38 Test Container (established) | Parallel Devstack (speculative) |
|--------|----------------------------------|--------------------------------|
| Setup time | ~10 min (one-time) | Hours (provision equivalent) |
| Data | Runner creates `test_*` DBs on the shared MySQL (server must be up) | Needs shared MySQL/Mongo |
| Memcached | Not used in tests | Must be separate (pickle issue) |
| LMS/Studio UI | Not available | Available at different ports |
| Purpose | Syntax+unit test verification | Full integration testing |
| Complexity | `docker run` + `paver test` | Full compose project |

---

## 5. Integration with Local Devstack

The Py2 devstack provides the "expected behavior" baseline. The Py38 test container verifies code correctness. They complement each other:

```
1. Make changes in platform/ (host)
2. Run targeted tests in Py38 container → verify syntax + logic
3. Run targeted tests in Py2 devstack → verify behavior unchanged
4. Compare results
```

### Running Same Test in Both Environments

```bash
# Py2 devstack
docker exec edx.devstack.lms bash -c '
  source /edx/app/edxapp/edxapp_env &&
  cd /edx/app/edxapp/edx-platform &&
  paver test_system -s lms -t path/to/test.py
'

# Py38 container
docker exec py38-tool-container bash -c '
  cd /work && source .venv/bin/activate &&
  paver test_system -s lms -t path/to/test.py
'
```

---

## 6. When You Might Need More

The lightweight container approach is sufficient for Phase 0–4 (per-module syntax and unit testing). Later phases may need:

| Phase | Need | Solution |
|-------|------|----------|
| Phase 5 (Integration) | Cross-module integration tests | Same container; paver test_system handles this |
| Phase 6 (Production) | Full LMS smoke test | May need a real LMS running under Py3; revisit then |
| XBlock testing | Some XBlocks need browser | Use Playwright on host pointing at devstack |

---

## 7. Quick Reference

```bash
# Start container
docker start -ai py38-tool-container

# Rebuild venv (if reqs changed)
cd /work && rm -rf .venv && ./.claude/skills/python3-migration/scripts/setup-py38-container.sh

# Run tests
cd /work && source .venv/bin/activate
SKIP_NPM_INSTALL=True paver test_system -s lms -t <module>
SKIP_NPM_INSTALL=True paver test_lib -C --fasttest

# Verify syntax only
python -m compileall -q <module_path>
```
