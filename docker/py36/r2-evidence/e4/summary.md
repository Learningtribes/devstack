# R2-preview E4 services evidence (2026-10-09)

Result: **PASS**. Final window `window-start.txt` .. `window-end.txt`
(2026-10-09T12:20:20Z .. 12:21:17Z), produced by `r2-e4-run.sh`.

## Identity

| Item | Value |
| --- | --- |
| Platform source | `platform-r2-py36-src` detached at `0ac3bfa6d09` (PR #2401 head), mounted read-only |
| Runtime image | `ltdps/edxapp:py36-r2-20261009` = `sha256:4560a9c2b264…` |
| Broker | `rabbitmq@sha256:4206c16c…`, vhost `py36-r2-20261009`, no host ports |
| Cache | `memcached@sha256:ec8ffdf1…` (dedicated; sessions are cache-only) |
| Services | LMS 127.0.0.1:18200, CMS 127.0.0.1:18210, solo-pool worker on `py36-r2.lms.default` |

Shared `edx.devstack.*` MySQL, Mongo, and Elasticsearch are used read-mostly
(login updates `last_login`); nothing Py3-pickled is written to the shared
session table or memcached.

## Gates

| Gate | Result | File |
| --- | --- | --- |
| LMS `/login`, `/heartbeat` | 200, 200 (modulestore/sql/elasticsearch OK) | `http-gate.txt` |
| CMS `/`, `/signin`, `/login_post`, authenticated `/`, `/heartbeat` | 302 → `/signin?next=/`, 200, 200 `success: true`, 200, 200 | `http-gate.txt` |
| CMS static `/static/studio/bundles/LoginFactory.js` | 200 `application/javascript` | `http-gate.txt` |
| Course enumeration + full-tree read | LMS 1 course, 6 blocks (published); CMS 1 course, 1 block (draft) | `course-*.txt` |
| Worker heartbeat, success, controlled failure, success | SUCCESS, SUCCESS, FAILURE (expected `RuntimeError`), SUCCESS | `tasks-pre-restart.txt` |
| Worker restart (`docker stop --timeout 15`) | Warm shutdown, exit 0 in 2 s; ready again | `worker-restart.txt` |
| Post-restart heartbeat, success | SUCCESS, SUCCESS; 45 tasks registered | `tasks-post-restart.txt` |
| Queues | `py36-r2.lms.default` 0 ready / 0 unacked / 1 consumer | `rabbit-queues.txt` |
| Log scan (LMS, CMS, worker, rabbit) | 0 Traceback / import / XBlock / HiddenDescriptor / HTTP 5xx / unregistered task / missed heartbeat; the only worker Traceback is the controlled failure | `log-*.txt` |

The two zero-consumer UUID queues are Celery 3.1 `rpc://` reply queues
(`RPCBackend.binding` declares `auto_delete=False`), one per client process.

## Findings resolved in the harness layer

1. **CMS authenticated root 500** (`ValidationError: 'course_org_filter' is
   required`, `contentstore/views/course.py` `course_listing`). Studio reads
   the org filter from the SiteConfiguration of the request host;
   `127.0.0.1:18210` matches no Site row (`site-inventory.txt`). Not an R2
   defect: R1 P1-A hit the same and used a configured host. `r2-e4-http.sh` now
   sends the canonical devstack hosts (`localhost:18000`, `localhost:18010`)
   instead of adding Site rows to shared MySQL.
2. **CMS static 404.** The runserver staticfiles handler serves only through
   finders, and the fresh source worktree has no webpack output
   (`common/static/bundles` is gitignored; only the Py2 `platform` checkout has
   a local build). The collected file exists in the read-only
   `devstack_edxapp_studio_assets` volume (`STATIC_ROOT`). LMS and CMS now run
   with `--nostatic`, so `/static/` reaches the `static(STATIC_URL,
   STATIC_ROOT)` route that both URLconfs add under `DEBUG`.
3. **Worker node name `@%h`.** A bare `WorkController` does not format the
   hostname; the worker now uses `socket.gethostname()`.
4. **Worker ignored SIGTERM** (first restart: exit 137 after 15 s). A bare
   `WorkController` installs no signal handlers, and the worker is container
   PID 1. The worker now installs Celery's `install_worker_term_handler` and
   `install_worker_int_handler`.

## Data drift since R1

Shared Mongo now holds a single course, `course-v1:QA+Acceptance+Test`
(created 2026-09-28; draft branch has no children, published branch has 6
blocks; `mongo-inventory.txt`). The 7 courses R1 counted, including
`course-v1:edX+XBlock101+2026`, are gone. The plan requires "course
enumeration and one course read", so E4 reads the existing course. The
CMS site org filter is `edX`, so the Studio home lists no courses for this
QA-org course. E6 browser specs that assume R1 course data must be checked
against this inventory first.
