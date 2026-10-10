# E6 groups 2-3 gate ports

## Discussion read/write (2026-10-10) - PASS on both runtimes

Port of R1 `provision-p1b-discussion-read-write.py` +
`tests/discussion_read_write.spec.ts` onto the E6 private stack
(`PY36_R2_E6_WITH_FORUM=1`): private MySQL, Mongo and Elasticsearch clones
plus a private comments service (`ltdps/forum@sha256:1f594e84...`) with a
generated key. The browser creates a thread, reads it, replies, hard-refreshes
and re-reads; postflight reads the thread back through the comments service and
finds both documents in the private `content` index.

| Runtime | Attempt | Result | Browser diagnostics | Service logs (LMS, CMS, forum) |
| --- | --- | --- | --- | --- |
| py36 | `discussion-py36/attempt4` | `E6_DISCUSSION_OK` | 0 console, 0 page, 0 failed, 0 HTTP errors | 0 lines |
| py27 | `discussion-py27/attempt2` | `E6_DISCUSSION_OK` | 0 console, 0 page, 0 failed, 0 HTTP errors | 0 lines |

Earlier attempts, kept as evidence:

| Attempt | Failure | Root cause and fix |
| --- | --- | --- |
| py36 attempt1 | provision `PluginMissingError: discussion` | Py3.6 image lacked the in-tree `xblock_discussion` distribution; fixed in the image (`../e6-discussion-image/summary.md`) |
| py36 attempt2 | thread-create request never sent | the devstack Django Debug Toolbar overlays the form's Submit button; E6 settings now drop `debug_toolbar` and `QueryCountDebugMiddleware`, as every R1 gate settings file did |
| py36 attempt3, py27 attempt1 | pass | superseded by the final runs after the static-serving fix below |

## Grading mutation (2026-10-10) - PASS on both runtimes

Port of R1 `provision-p1b-grading-mutation.py` +
`tests/grading_mutation.spec.ts` (`r2-e6-grading.sh` / `r2-e6-grading.py`)
onto the E6 stack started with `PY36_R2_E6_WITH_BROKER=1`: a private
`rabbitmq:3.8-management` (`sha256:4206c16c...`, 512 MiB cap, vhost = stack
namespace, generated credentials in `.py36-r2-config/e6-broker.env`, mode 600)
and a grade/progress worker (`r2_e6_grading_worker.py`: the R1 worker plus
SIGTERM/SIGINT handlers). LMS, scripts and worker run with eager Celery off
and the R1 exchange, queue and routing-key layout under the stack namespace;
Studio stays eager. The shared `edx.devstack.rabbitmq` is not used.

Flow: provision -> reset/preflight (idle queues, exactly one consumer per
grading queue, one worker, required tasks registered) -> Chromium wrong answer
and Progress 0/1 -> the wrapper waits for the worker log to show the expected
successes and runs midcondition once -> release -> Chromium correct answer,
Progress 1/1, reload -> postflight.

| Runtime | Attempt | Result | Browser diagnostics | Tasks grade / progress (mid, post) | Course grade | Service logs (LMS, CMS, worker) |
| --- | --- | --- | --- | --- | --- | --- |
| py36 | `grading-py36/attempt2` | `E6_GRADING_OK` | 0 console, 0 page, 0 failed, 0 HTTP errors | 1/1, 2/1, 0 retries | 0.0 -> Pass 1.0 | one INFO cohort-cache line |
| py27 | `grading-py27/attempt1` | `E6_GRADING_OK` | 0 console, 0 page, 0 failed, 0 HTTP errors | 1/1, 2/1, 0 retries | 0.0 -> Pass 1.0 | same INFO line |

Both worker logs carry the same `graders.py:181 Invalid arguments for a
subgrader: available_count` WARNING twice; it comes from the R1 fixture's
grading policy and is runtime-neutral.

Earlier attempt, kept as evidence:

| Attempt | Failure | Root cause and fix |
| --- | --- | --- |
| py36 attempt1 | spec `visible grading unit`: `.unit-title` resolved but hidden | the `hawthorn` theme bound to `localhost:18000` hides `.xblock .unit-title` (`src/themes/hawthorn/lms/static/sass/_courseware.scss:818`); R1 ran on an unthemed per-gate site. With owner approval, `r2-e6-grading.py` provision deletes that site's `SiteTheme` row in the private clone (`E6_GRADING_UNTHEMED`); `SiteTheme.get_theme` reads per request, so no restart. Theme coverage stays with group 1 |

Stack fixes found on the way (not gate failures):

- RabbitMQ died at boot with `.erlang.cookie: eacces` on one start: the
  readiness probe ran `rabbitmq-diagnostics` as root, and when it won the race
  with the server it created a root-owned cookie. The probe now runs as
  `rabbitmq`.
- `docker rm -f` left the anonymous volumes the RabbitMQ, ES (`data`) and
  Mongo (`configdb`) images declare; cleanup now uses `docker rm -f -v`. The
  host dangling-volume count (82) did not grow across the two grading stacks.
  Volumes leaked by earlier E6 runs cannot be told apart from other dangling
  volumes and were left alone.

## Studio edit/publish (2026-10-10) - py27 PASS; py36 browser PASS, service log FAIL on a master Python 3 defect

Port of R1 `provision-p1b-studio-edit-publish.py` +
`tests/studio_edit_publish.spec.ts` (`r2-e6-studio.sh` / `r2-e6-studio.py`)
onto the default E6 stack (eager Celery, private ES, no forum or broker).
Differences from R1:

- Sites: R1 renamed fixed Site ids to per-gate domains and replaced their
  configuration. E6 keeps the clone's canonical `localhost:18010` (id 5) and
  `localhost:18000` (id 4) rows and merges `course_org_filter=QA` and
  `ENABLE_LAST_ACTIVITY=True` into their existing values (`E6_STUDIO_SITE`
  lines in `provision.log`; Studio was `edX`). Studio's course listing reads
  `course_org_filter` through runserver's cached Site, so provision runs as the
  new `PY36_R2_E6_PRESTART` step of `run-r2-e6-services.sh` (after the fixture,
  before the servers) with CMS settings (`PY36_R2_E6_SCRIPT_SERVICE=cms`).
  The global fixture is unchanged, so group 1's Studio checks keep `edX`.
- External calls: the spec runs its service script at midcondition and
  postflight. The browser container has no Docker, so
  `BROWSER_STUDIO_SERVICE_SCRIPT` is `r2-e6-handshake.sh`, which files a
  request under the harness output; the wrapper answers it on the host by
  running the provisioner action on the CMS side and returns its output and
  exit status.
- Credentials: author and learner passwords are generated into
  `.py36-r2-config/e6-studio.env` (mode 600) and passed with `--env-file`;
  `r2-e6-browser.sh` now writes `<redacted>` for every `*PASSWORD*` name in
  `browser-identity.txt`.
- The courses are QA-org; the Studio site stays themed (`hawthorn`); the spec
  had no theme conflict there.

| Runtime | Attempt | Result | Browser diagnostics | External steps | Service logs (LMS, CMS) |
| --- | --- | --- | --- | --- | --- |
| py36 | `studio-py36/attempt2` | `E6_STUDIO_OK` (24.0 s) | 0 console, 0 page, 0 failed, 0 HTTP errors | `MIDCONDITION_OK`, `STUDIO_POSTFLIGHT_OK` | INFO cohort-cache line; **CMS `ERROR` + traceback at publish (below)** |
| py27 | `studio-py27/attempt1` | `E6_STUDIO_OK` | 0 console, 0 page, 0 failed, 0 HTTP errors | `MIDCONDITION_OK`, `STUDIO_POSTFLIGHT_OK` | same INFO line only |

No 4xx/5xx in either runtime's LMS or CMS access log.

**Python 3 defect (master line, not R2):** on publish the eager
`update_search_index` task fails on Python 3.6 with
`AttributeError: 'dict_items' object has no attribute 'extend'` at
`cms/djangoapps/contentstore/courseware_index.py:398` (`fetch_group_usage`
calls `.extend()` on `dict.items()`). The same line is on `origin/master`
(last touched by #2361). `index()` logs it and aborts the whole course
reindex, so on Python 3 Studio publishes never update `courseware_index`;
py27 issued two `POST /_bulk 200` for the same flow. R1 used a mock search
engine and did not reach this line. Per the 21:00 decision this goes to a
master owner PR / Track E card, not #2401. Owner decision (2026-10-10
15:50): the gate counts as a PASS for the R2 question on both runtimes.

Earlier attempt, kept as evidence:

| Attempt | Failure | Root cause and fix |
| --- | --- | --- |
| py36 attempt1 | 32 console errors on Studio pages: 404 for `/static/css/{noto,foundever}-sans.css` and `/static/fonts/NotoSans/*` (the publish flow itself completed) | the `hawthorn` theme's fonts partial (`src/themes/hawthorn/common/static/sass/_fonts.scss`) and `common/static/css/noto-sans.css` (#1683) reference `/static/css/` and `/static/fonts/` absolutely, outside Studio's `/static/studio/` `STATIC_URL`. Production nginx serves the whole `/static/` prefix from the shared collected tree on the Studio host too; the E6 handler only covered `STATIC_URL`. R1 avoided it by setting Studio's `STATIC_URL` to `/static/`. Fix in `r2_e6_wsgi.py` (next section) |

## Harness fix: static files served ahead of Django

After the toolbar removal, the py27 group 1 control showed bursts of LMS
`/static/...` 500s with `OperationalError (1040, 'Too many connections')` on
the private MySQL and failed one extra surface (26/30). Measured on the running
stack: the CMS process held 89 sockets with only its main thread left; 40
concurrent unauthenticated static requests added about 35 that never closed,
sequential requests added none.

The cause is the E4/E6 `--nostatic` choice combined with a Django 1.11 defect
present in both 1.11.15 and 1.11.29. With `--nostatic`, `/static/` goes
through the URLconf `static()` route and therefore through the full middleware
stack, which queries MySQL. `WSGIHandler` then replaces the `FileResponse` with
`wsgi.file_wrapper(response.file_to_stream)`, so `HttpResponse.close()` and
`request_finished` never run, and `close_old_connections` never closes that
thread's connections. They stay open until cyclic GC frees the dead thread's
`DatabaseWrapper`. Stock devstack does not hit this because its runserver keeps
the static handler, which answers before the middleware. Production nginx
serves `/static/` before Django as well.

Fix (harness only): `r2_e6_wsgi.py`, wired through `WSGI_APPLICATION`, wraps
the same `get_wsgi_application()` object that runserver would otherwise use. It
answers `STATIC_URL` from `STATIC_ROOT` with the same
`django.views.static.serve` view that the URLconf route uses, so finders,
`STATIC_ROOT` and theme URL resolution are unchanged. Checks on py27:

- response bytes equal the collected files for LMS and CMS assets;
- a missing file still returns 404;
- 60 concurrent static requests leave the CMS socket count at 6.

The private MySQL keeps the shared server's configuration (`mysql:5.6`, default
`max_connections` 151); it was not raised.

Studio gate follow-up: the handler now answers `/static/<path>` from
`STATIC_ROOT_BASE/<path>` (the shared tree both services mount) instead of
`STATIC_URL` from `STATIC_ROOT`, matching nginx on the Studio host. For LMS the
two are identical (`/static/`, `STATIC_ROOT == STATIC_ROOT_BASE`); for Studio,
`/static/studio/<x>` maps to the same file and the previously unserved
`/static/css|fonts/...` now resolve. Checked on py36: five LMS/Studio assets
byte-equal to the collected files (including `/static/css/noto-sans.css` and a
NotoSans font on 18010), missing files 404, `..` traversal rejected by
`safe_join` (`SuspiciousFileOperation`, same view as before).

## Group 1 under the final settings

| Runtime | Result | Failures | Service logs |
| --- | --- | --- | --- |
| py36 | 27/30 | p1b-dashboard last-activity x2 (R1 fixture mismatch), pr-2396 chooser 404 (accepted) | one INFO cohort-cache line |
| py27 | 27/30 | same three | same INFO line |

Evidence: `../e6-discussion-image/group1-{py36,py27}/`.

## Isolation

The shared Elasticsearch had the same index list, document counts and
`index_total=0` / `delete_total=0` before the clone, after the clone, after
the discussion gates, after the grading gates and after the Studio gates. No shared container was
started, stopped or written. A secret scan of `docker/py36` (scripts and
evidence) and the gate log root for the MySQL, forum and broker secrets found
no match; the same scan with the Studio author/learner passwords added found
no match in the Studio evidence, which contains no Playwright trace archive.
