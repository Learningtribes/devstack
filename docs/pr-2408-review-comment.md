## Review and local verification (`6417575bed5`)

153 files, +1,510/−467 against master `98e8d5ad493`. Text/bytes and iterator fixes for Capa, xmodule, courseware, grades, CSV, discussion, Studio, cookies, and templates. On Python 2.7 these are no-ops when they are correct, so a green page only counts if the same URL also succeeds on master. No path overlap with #2406 or #2407.

### Review

- Templates and views replace `unicode(...)` with `text_type(...)`, and `from urllib import urlencode` with `six.moves.urllib.parse`. Course about, course home, progress, and courseware all returned 200 with the fixture course title / course key in the body, so those Mako and view paths resolve.
- `courseware/views/index.py` wraps `TEMPLATE_IMPORTS.items()` in `list()` before building the accordion context. Courseware returned 200.
- `grades/course_grade.py` swaps `chapter_grades.itervalues()` for `.values()`. Progress returned 200; that path walks chapter grades when computing completion / subsection maps.
- `SafeCookieData` is `@python_2_unicode_compatible`, uses `__str__`, and hashes with `.encode('utf-8')` / `b'|'`. `/heartbeat` returned 200 with the middleware on the stack.
- `XModuleDescriptor.__hash__` is added alongside `__eq__` so set/dict use stays consistent under Python 3. Studio `/home/` returned 200 (xmodule still loads).
- `get_current_child` defaults `min_depth` to `0` when callers pass `None`, which avoids comparing against `None` under Python 3. Courseware still navigates on this fixture.
- CSV writers (`instructor_analytics/csvs.py`, `dashboard/sysadmin.py`) use `BytesIO` / `six.text_type` encoding helpers and a Py2-safe `quotechar`. Not hit over HTTP; those run only on export.
- Discussion views replace `unicode` / `iteritems` with `text_type` / `.items()`, and stabilize vendor JS deps with `OrderedDict.fromkeys`. Not asserted in the browser: `edx.devstack.forum` is stopped, so the forum GET is the maintenance-path 500 already seen on Wave 2, not an import proof.
- Dashboard course-card / last-activity templates were also updated (`text_type`, locale default, removal of the empty `course_url` fallback). They did not execute on `localhost`: `qacert` is enrolled in org `QA`, but the site `course_org_filter` hides that org, so the dashboard renders the empty last-activity state. The footer (`timezone.localtime` year) did run and returned 200 with `Copyright` / `Foundever`.
- Not hit over HTTP: edxnotes service calls, word cloud, video transcripts, vertical validation, git course import, and sysadmin CSV download. The fixture course has no such blocks.

### Browser gates (local Python 2.7 devstack)

Checklist `pr-2408.yml` on `ltdps` m5-fixed, `PLATFORM_MOUNT` pointed at `e7-wave3-subsystems` and then at master. **7/7 passed on both**, twice on 2026-10-14 (first run 8.2s / 9.5s; rerun 9.1s / 14.0s). Every surface passes on both trees, so none is a discriminator.

| Surface | Wave 3 | master |
|---|---|---|
| `GET /heartbeat` | 200 | 200 |
| `GET /dashboard` | 200, body contains `Copyright` / `Foundever` | 200 |
| `GET /courses/{course}/about` | 200, body contains `QA Acceptance Test` | 200 |
| `GET /courses/{course}/course/` | 200, body contains title and course key | 200 |
| `GET /courses/{course}/progress` | 200 | 200 |
| `GET /courses/{course}/courseware` | 200 | 200 |
| Studio `GET /home/` | 200 | 200 |

Evidence: `devstack/docs/pr-2408-verification.md`. After each run, harness `FEATURES` blocks were reverted on both trees and the stack was remounted to `platform-e7-wave1-startup` (pre-run mount). After the rerun, LMS `/heartbeat` and Studio `/signin` were both 200.

### CI on this head

- Python 2.7 syntax, Python 3 syntax, and test isolation: pass.
- Jenkins: no status reported on `6417575bed5`.
- Python 3.6 LMS/CMS `check`: not run. These gates do not prove the Python 3.6 import path.
