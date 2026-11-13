# Replay constant inventory

| Historical entry/value | Replacement or retained scope |
| --- | --- |
| run42 `run.py` environment/output directory | Required JSON config; evidence SHA bound to every command |
| run42 `run_check.py` default runtime container | Required `runtime_container`; exact ownership label checked |
| Post-command duplicate-label assertion | Exclusive output reservation before execution |
| run42 `replay_after_install.py` container/startup absolute paths | Container from config; startup from committed export root |
| SQL creator fixed database assertion | New MySQL container/data volume initialized with configured `database` |
| Mongo database/cache/ES/queue prefixes | Explicit config forwarded to existing local settings |
| Old process inherited `PY313_*` environment | Discarded; rebuilt only from contract plus protected service secrets |
| Old test SQL name | Explicit `test_database`, forwarded as `PY313_TEST_DATABASE_NAME` |
| Course seed/persistence fallback | Explicit `course_key` forwarded as `PY313_ACCEPTANCE_COURSE_ID` |
| Runtime/volume/service/network names and ports | Configured, required run-id association, preflight existence rejection |
| Runtime image / infrastructure image tags | Runtime is a local sha256 image ID; six services use the reviewed multi-platform OCI index digests in `infrastructure-images.lock.json`; audit validates normalized registry digest identity and records selected IDs, source metadata and platforms |
| JWT and acceptance fixture paths | Explicit private file paths, read-only mounts; values excluded/redacted |
| run42 `audit_final_inputs.py` export/repo paths | Audit reads configured export identity and checks runtime sources |
| run42 `collect_and_scan.py` trace path/run42 worker names | Current config worker logs only; failed commands already captured locally |
| `/startup`, `/input/platform` | Retained internal mount contract; each runtime/volume is new |
| Former `/runtime/platform-source`, `/runtime/venv`, `/runtime/<name>` | `/edx/app/edxapp/edx-platform`, `/edx/app/edxapp/venvs/edxapp`, `/edx/app/edxapp/py313/<name>` (`APP_ROOT` in `core.py`, Platform `ci/py313/layout.py`); `fresh_preflight` refuses a Platform without that module |
| Former `/runtime/rebuild-sources-20261025-run25` build staging | Removed; package inputs are Platform pins and companions, installed by `ci/py313/install.py` |
| Internal static/theme/xmodule/wheel paths | Existing build contract inside each fresh runtime; exported sources audited |
| `start_http.py` / `start_worker.py` legacy defaults | New entry supplies explicit environment and checks ownership before invoking; no fallback is used |
| Historical evidence scripts and restart PIDs | Preserved verbatim; not dispatched by this runner |
