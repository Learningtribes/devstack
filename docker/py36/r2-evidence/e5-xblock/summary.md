# E6 follow-up - ilt-xblock and xblock-pdf in the Python 3.6 lock; E2-E5 re-gates (2026-10-10)

Owner decision (2026-10-10): add `ilt-xblock` and `xblock-pdf` to the Python
3.6 lock, rebuild the runtime, re-run E2-E5. The wider `xblock.v1` gap (47 vs
95 entry points on Python 2.7, e.g. `edx-sga`) stays out of scope.

## Lock and image

| Item | Value |
| --- | --- |
| Lock | `0d17f2a`: `xblock-pdf@99b22d45` in `py36-git-requirements.txt`; private `Learningtribes/xblock-ilt@52b0f1cb` (hawthorn tip, contains "New ILT (#44)" that Platform `IltGlobals` / New ILT #2224 expects) installed in the Dockerfile from the `xblock_ilt` build context, content digest checked against `XBLOCK_ILT_TREE_SHA256`, entry points `ilt` + `pdf` asserted |
| ilt source | `r2-export-xblock-ilt.sh`: SSH clone, ancestor-of-`origin/hawthorn` check, `git archive` to `.py36-r2-sources/xblock-ilt-52b0f1cb…` (read-only, `.identity`: 40 files, content sha256 `fc209332…`). The user's `src/xblock-ilt` (`5e904e38`) is older and fails on Python 3 at `ilt.py:220`; not used, not modified |
| Build | attempt 3, no-cache, 11:58-12:10, exit 0. Attempts 1-2 lost a GitHub TLS handshake (`gnutls_handshake() failed`, Debian git through the proxy; host git unaffected). Fix `521cc5d`: `r2-mirror-git-sources.sh` fetches the 21 pinned commits into host bare repos, the build reads them through `url."file:///git-mirror/".insteadOf "https://github.com/"` (lock URLs and pip metadata unchanged; every SHA verified) |
| New runtime | `ltdps/edxapp:py36-r2-20261009` = `sha256:9b43579930c4cd53e77e1fc5cfe1100f8852c605f1dfa8e9ab924fa2503f2211` (arm64, local only); previous `8c2e7df2e03d` kept as `py36-r2-20261009-pre-ilt` |
| Py3.6 runner | `sha256:5187413ae4b1` (base layer prefix 27/33 OK); Py2.7 runner unchanged `e5ecccf98eb9` |

## Gates

| Gate | Result | Evidence |
| --- | --- | --- |
| E2 `pip check` | No broken requirements | `e2-rebuild/pip-check.txt` |
| E2 freeze | 223 lines; vs the Markdown rebuild exactly `+ilt-xblock==0.3`, `+xblock-pdf===v1.0.2-rg` | `e2-rebuild/freeze-diff-vs-markdown.txt` |
| E2 site-packages compile | same 3 accepted paths, path-set sha256 `cc0d80d8…` | `e2-rebuild/site-packages-compile*` |
| E2 entry points | one `edx_proctoring`; `xmodule.v1` 35 / 0 failures; `xblock.v1` 47 (was 45): `ilt` = `ilt.ilt.ILTXBlock`, `pdf` = `pdf.pdf.PdfBlock`; CMS 0 load failures. Under plain `lms.envs.test` `scormxblock` fails (`xblock_config.models.StudioConfig` not in `INSTALLED_APPS`) - identical on the Python 2.7 control, so pre-existing | `e2-rebuild/entry-points.txt`, `e2-rebuild/scorm-lms-test-py27-control.txt` |
| E3 LMS / CMS check | exit 0, only the two known `urls.W005`; CMS no issues | `e3-rebuild/` |
| E3 import smoke | LMS 122/122, CMS 7/7, 0 XBlock load failures | `e3-rebuild/import-smoke-*.txt` |
| E4 services (window 04:35Z) | HTTP gate 40 lines as E4 (only the authenticated Studio `/` size moves by 2 bytes, token); course read payload identical (LMS/CMS 5 lines); tasks SUCCESS/SUCCESS/FAILURE(controlled)/SUCCESS, post-restart SUCCESS x2; queues as E4; logs: only the controlled-failure traceback | `e4-rebuild/` |
| E5 Py3.6 identity + controls | focused 118, p1b-batch1 109, p1b-batch2 38 passed; normalized node lists identical to `e5-markdown` | `final/*-py36.txt` |
| E5 Py3.6 r2-dcc | 85 failed / 274 passed / 13 skipped / 2 collection errors; failure set, 372-node list and classifier output (87 sections, all master lines) byte-identical to `e5-markdown` | `final/r2-dcc-*.txt` |

`ilt` imports open `TimedRotatingFileHandler('/edx/var/log/lms/ilt_xblock.log')`
at import time (`ilt.py:74`), so every container needs that directory; the
E2/E3 harnesses and the asset builder create it.

## Incident: shared Mongo OOM-killed (2026-10-10 03:28:08Z)

`edx.devstack.mongo` exited 137 with `OOMKilled=true` while this work ran the
no-cache build, the amd64-emulated webpack compile and eight E6 containers in
the 15.67 GiB OrbStack VM. The first E4 rerun then failed its heartbeats
(`e4-attempt1-shared-mongo-oom/`). With owner approval the same container was
started again (`docker start`, same volume); mongod recovered from its last
checkpoint (journal is disabled in this devstack), `QA/Acceptance/Test` intact
(last edit 2026-09-28, both branch structures present), master LMS heartbeat
200. Prevention: gate containers now carry cgroup caps (`--memory`: services
2g, MySQL clone 2g, runner 4g, asset builder 6g, memcached 128m, rabbitmq
512m) and heavy steps run one at a time.

## Verdict

The two XBlocks are in the runtime and every identity-sensitive E2-E5 gate is
unchanged apart from the intended additions.
