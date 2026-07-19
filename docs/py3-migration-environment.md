# Python 3 Migration — Devstack Environment Strategy

> Date: 2026-07-19  
> Reference: `platform/.claude/skills/python3-migration/` + `CLAUDE.md § Python 3.8 Testing`  
> **⚠️ Corrected:** The migration project already defines a Py3 testing strategy — a lightweight test container, NOT a parallel devstack. This document replaces the earlier original-design speculation with the established project approach.

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
| **Network host mode** (`--network host`) | Access existing devstack's MySQL/Mongo/ES when needed |
| **Source bind-mount** | Code changes visible instantly; no rebuild |
| **`.venv` on host** | Persists across container restarts; no repeated pip install |
| **No services** | `paver test_system` uses test databases (auto-created by Django test runner) |
| **No data sharing** | Test runner creates/destroys test databases; no conflict with Py2 devstack |

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

### 3.1 Per-Module Test

```bash
# Inside container
cd /work && source .venv/bin/activate

# Run a specific module test
paver test_system -s lms -t lms/djangoapps/grades/tests/test_models.py

# With fast options
paver test_system -s lms -t lms/djangoapps/grades \
  --disable-migrations --fail-fast
```

### 3.2 Syntax Verification

```bash
# Verify a module compiles under Py3
python -m compileall -q lms/djangoapps/<module>/
# Exclude migrations
find lms/djangoapps/<module> -name "*.py" ! -path "*/migrations/*" \
  -exec python -m py_compile {} \;
```

### 3.3 Full Suite

```bash
SKIP_NPM_INSTALL=True paver test_system -s lms
SKIP_NPM_INSTALL=True paver test_system -s cms
SKIP_NPM_INSTALL=True paver test_lib -C --fasttest
```

---

## 4. Comparison: Test Container vs Parallel Devstack

| Aspect | Py38 Test Container (established) | Parallel Devstack (speculative) |
|--------|----------------------------------|--------------------------------|
| Setup time | ~10 min (one-time) | Hours (provision equivalent) |
| Data | Test runner auto-creates clean DB | Needs shared MySQL/Mongo |
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
