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

## Group 1 under the final settings

| Runtime | Result | Failures | Service logs |
| --- | --- | --- | --- |
| py36 | 27/30 | p1b-dashboard last-activity x2 (R1 fixture mismatch), pr-2396 chooser 404 (accepted) | one INFO cohort-cache line |
| py27 | 27/30 | same three | same INFO line |

Evidence: `../e6-discussion-image/group1-{py36,py27}/`.

## Isolation

The shared Elasticsearch had the same index list, document counts and
`index_total=0` / `delete_total=0` before the clone, after the clone and after
the discussion gates. No shared container was started, stopped or written.
