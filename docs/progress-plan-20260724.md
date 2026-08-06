# Py3.6 Migration — Progress Report & Handoff

> Status: HISTORICAL R27 STATUS SNAPSHOT
>
> Current cross-repository state and assignments live in the
> [migration Hub](https://github.com/Learningtribes/platform/tree/migration_discussion/docs/migration_discussion).
> New volatile state is recorded there; this file preserves the R27 snapshot.
>
> **Historical snapshot:** 2026-07-28 · Container: `ltdps/edxapp:py36` / `py36-build` · Branch: `py36-boot-fixes` · HEAD: `fcac4469cf7`
>
> Git status at snapshot: `origin/py36-boot-fixes...HEAD = 0/0`; the branch is pushed and is 25 commits ahead of `origin/master`. The 55-file Py3 batch is committed in `9e1bd6f86a3`; the follow-up compatibility batch is committed in `fcac4469cf7`; the platform worktree contains only one unrelated deleted CSV, which must not be staged.

## Historical review status (2026-07-28)

**Historical R27 state; not current execution status.** The older `721/1446/586`, `11 commits/unpushed`, and `637/827/626` figures are historical checkpoints, not stable current-state claims. Commit `9e1bd6f86a3` only records the 55-file working-tree state used for that baseline; it does not change the measured code state.

The follow-up commit `fcac4469cf7` contains the next 41-file Py3 compatibility batch. It was pushed after targeted verification. No new full-suite total is claimed for this commit: the canonical full run reached 80% and was stopped after 21 minutes without progress in the xmodule/contentstore region. Keep the historical baseline unchanged until a complete run finishes.

## Test Baseline

| Milestone | Failed | Passed | Errors | Notes |
|------|:---:|:---:|:---:|------|
| R18 tox baseline | 798 | 821 | 613 | Gap C milestone |
| +decode+unicode | 566 | 898 | 626 | |
| +broad sweep (review) | 737 | 1430 | 586 | ur/<>/long/reduce/unicode/basestring |
| +import six (151f) | 722 | 1445 | 586 | Historical checkpoint |
| Current committed baseline `9e1bd6f` (`--tb=no`) | 722 | 1445 | **586** | 84 skipped; same measured working-tree state |
| Current committed baseline `9e1bd6f` (canonical `--tb=line`) | **720** | **1447** | **586** | 84 skipped; same measured working-tree state |
| R33 collection-only after follow-up fixes | — | **12464 collected** | **81 collection errors** | Same collection result as R32; no runtime total claimed |
| **Observed current range** | **720–722** | **1445–1447** | **586** | Same code state; one/two test drift |
| **Net Δ from R18 (canonical)** | **−76** | **+626** | **−27** | 52.5% pass rate vs 36.8% at R18 |

The current full-run pass rate is approximately 52.4–52.6%, versus 36.8% at R18: **+15.6–15.8 percentage points**. The previous “76% pass rate increase” label was the relative increase in passed-test count, not the pass rate. “816 tests never ran before” is not retained because no per-test identity comparison was recorded.

**Canonical collection-only:** 12464 tests collected, 81 collection errors. The separate 2251/572 collection figures came from a different command and are not mixed into this canonical count. The full-run `586 errors` includes collection/setup errors and must not be presented as collection-only errors. Boot + check: 0 issues.

### Baseline stability note

The same HEAD produced `722/1445`, `721/1446`, and `720/1447` failures/passes across equivalent full-suite invocations. The latest canonical `--tb=line` run is `/tmp/tbline-current-ignored.txt`; the only named test that changed between the two fresh `--tb=line` runs was `openedx/core/djangoapps/site_configuration/tests/test_models.py::SiteConfigurationTests::test_get_all_orgs`. Do not count a one-test swing as migration progress; isolate this order/state sensitivity first.

## Completed

- ✅ Django 1.11.29 + celery 3.1.25 + kombu 3.0.37 + Py3.6 boot
- ✅ 7 pip constraints (Django/celery/kombu/pymongo/mongoengine/mysqlclient/DRF)
- ✅ kombu.async OK (async = soft keyword on 3.6)
- ✅ Boot-path blockers addressed: Django setup and system check succeed on Py3.6
- ⚠️ Repository-wide Py2 residue remains in tests and deferred/low-import paths (`str.decode`, `StringIO`/`cPickle`, Python 2 `print`, and related import compatibility)
- ✅ `ltdps/edxapp:py36` image (3.87GB)

## 2026-07-27 source follow-up (committed in R26)

- Fixed a coherent xmodule/CAPA/grades/graph Py3 batch in `common/lib/xmodule/xmodule/modulestore/xml.py`, `capa_base.py`, `capa_module.py`, `common/lib/capa/capa/`, `common/djangoapps/util/memcache.py`, `lms/djangoapps/grades/`, and `openedx/core/lib/graph_traversals.py`: missing `six` imports, iterator `.next()`, text-to-hash conversion, `dict_keys` indexing, bytes/text XML and HTML boundaries, LTI body hashing, and the broad-regex regression `encoding='six.text_type'`.
- Follow-up fixes covered WebOb request/response bodies, deterministic video transcript export ordering, Python-version-specific LTI float errors, and a transcript filename formatting bug in `video_module/transcripts_utils.py`.
- Static verification passed: modified Python source/test files compile in `py36-build`; `git diff --check` passed. The host `uv` executable is currently blocked by a local SystemConfiguration runtime panic, so the container result is the authoritative compile check.
- Container verification on 2026-07-27: boot + `check` returned `0 issues`; the focused memcache/grades/site/ACE set passed **68** tests; LTI 1.1/2.0 plus video XML export passed **50** tests; `test_import.py` passed **25** tests.
- The CAPA collection blocker in `checker.py` is fixed. `test_inputtypes.py` now passes **60** tests; full `test_capa_problem.py` passes **40** and has **3** failures, all from the external codejail package's Python-2-only `long` reference. The pinned `pysrt==0.4.7` package still uses Python-2 builtins, and Mongo-backed video tests still cannot run while the container cannot reach Mongo at `localhost:27017`.
- The larger combined regression reached 91% and then stopped producing output in the XML/content-store path; its pytest process was terminated after 7:30. A follow-up isolated the wait to the Mongo hostname and verified the targeted path with `edx.devstack.mongo`; this produced no new full-suite total, so keep the existing `720/1447/586` baseline unchanged.
- The 55-file source batch was committed as `9e1bd6f86a3` without changing its measured code state. The only remaining platform worktree change is the unrelated CSV deletion, which remains untouched.

## 2026-07-28 review continuation

- Fixed the remaining PyMongo 3/GridFS paths in `contentstore/mongo.py`: `.client`/legacy `.connection` lookup, database-name drops, bytes/text/file-stream writes, aggregate command cursors, and `UpdateResult.matched_count`.
- Fixed Mongo module-store traversal when `depth=None` and restored the dict-like `.items()` API on `CourseAssetsFromStorage`.
- Updated the XML unicode regression test to read the fixture in binary mode before asserting that ASCII decoding fails.
- Targeted regression with `EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo`: `test_contentstore.py` **14 passed**, `test_mongo.py` **54 passed**, `test_xml_importer.py` **7 passed**, and `test_xml.py` **5 passed / 1 environment failure**. The combined run (excluding only the confirmed DAG plugin failure) was **80 passed / 1 deselected**.
- The XML/content-store hang was configuration-related: `localhost:27017` is unavailable in `py36-build`; the running service is `edx.devstack.mongo`. This is no longer a blocker for targeted Mongo tests when the host variable is set.
- The DAG failure is an external test-container dependency gap: `discussion` raises `PluginMissingError`, and the repository's `xblock-discussion` source additionally needs the missing `xblockutils` package. The asset XML test is blocked during collection by the legacy nose `attr`/pytest `MarkGenerator` incompatibility.
- Independent read-only review approved the handoff with no Critical/Major findings. Minor follow-ups were recorded for the broad `NameError` catch in `video_module.py:994-1001` and self-derived expected values in `capa/tests/test_inputtypes.py:748-753`; neither blocks this batch.

## 2026-07-28 execution follow-up (`fcac4469cf7`)

- Fixed the next 41-file Py3 batch: legacy imports/stdlib codecs, test bytes/text boundaries, the callable legacy nose `attr` shim, and the remaining verify_student/shared base64 paths.
- `verify_student/ssencrypt.py` now produces byte AES IVs, documents RSA plaintext as bytes, returns text signatures, and keeps canonical signing payloads as text. `verify_student/models.py` and `image.py` use explicit base64 APIs; `common/djangoapps/util/models.py` uses `base64` plus `io.BytesIO` for compressed text data.
- Targeted verification in `py36-build`: verify_student encryption/signing **5 passed**; image and compressed-text base64 smoke **passed**; modified Python files compile; Django `check` reports **0 issues**; `git diff --check` passed.
- R33 collection-only: **12464 collected / 81 errors**, unchanged from R32. The full run with `EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo` reached 80% and was stopped after 21 minutes with no progress; no new failed/passed/error total is recorded.
- Commit `fcac4469cf7` is pushed (`origin/py36-boot-fixes...HEAD = 0/0`). The unrelated survey CSV deletion remains unstaged.

## Remaining work: separate queues

- **720–722 runtime test failures** from repeated current-HEAD full runs.
- **81 collection errors** from the current canonical collection-only run (`12464 collected`); the separate `2251/572` figures are not mixed into this queue.
- **14 additional full-run errors** occur after collection/setup; classify them separately rather than folding them into either queue.
- **Targeted dependency/runtime blockers:** codejail `long`, pysrt `unicode`/`basestring`, missing discussion XBlock/xblockutils, and the legacy nose/pytest `MarkGenerator` collection incompatibility. Mongo is usable with `EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo`.
- ORA2/openassessment is the highest-risk deferred runtime dependency. The four separate prod-gate classes are SAML, coursegraph, enterprise, and JWT.

The earlier root-cause table mixed runtime failures with collection errors. The latest canonical `--tb=line` clustering is now available; hit counts below are raw log occurrences, not unique tests.

| Hits | Root Cause | File |
|:---:|------|------|
| 377 (354 `E` lines) | `str.decode` | Collection errors; test files |
| 131 | `KeyError: 'en'` | Runtime traceback; Django i18n resolver |
| 50 (47 `E` lines) | `MarkGenerator` not callable | Collection errors; templates/tests |
| 44 | bytes-like object required | Runtime traceback; capa/XML/upload paths |
| 45 | `dict_keys` does not support indexing | Runtime traceback; draganddrop/capa |
| 42 | Unicode objects must be encoded before hashing | Runtime traceback; memcache/provider/grades |
| 3 CAPA problem failures | external/runtime compatibility | installed codejail `long` |

The `USE_I18N` attempt was reverted after a regression. Do not reapply it without a targeted resolver test and a fresh full baseline.

The hit-count table above is from the earlier 586-error full-run clustering. R33's 81 collection errors are a narrower, command-specific set; use the R33 collection log for current classification rather than carrying those raw hit counts forward.

## Blockers

| Item | Status | Action |
|------|:---:|------|
| 720–722 failures + 81 collection errors | Split runtime/collection queues | Isolate order-sensitive test, then fix top clusters |
| Focused batch | ✅ partially verified | 68 core + 50 LTI/video + 25 import + 60 CAPA inputtypes passed; CAPA codejail/pysrt and test-collection blockers remain isolated |
| Canonical full rerun | Not complete | XML/content-store wait is isolated; provision remaining dependencies/collection fixes before rerunning |
| Py3.6 dependency/runtime blockers | Open | Patch compatible codejail/pysrt or provision replacements, discussion XBlock/xblockutils, and pytest-nose compatibility; then rerun |
| ORA2/6F (~70K SLOC) | Deferred | Patch/wait/replace decision |
| DCC #2322/#2323/#2324 | Historical APPROVED snapshot | Refresh external PR status |
| DCC #2348 | Historical REVIEW_REQUIRED snapshot | Refresh external PR status |
| 4 prod-gate stubs | Deferred | SAML/coursegraph/enterprise/jwt — prod config check |
| Branch push | ✅ pushed (`0/0` ahead of origin) | No push action required until the next commit |
| Worktree | ⚠️ unrelated CSV deletion | Resolve ownership before staging |

## Worktrees & Branches

| Worktree | Branch | Status |
|------|------|:---:|
| `platform` (active) | `py36-boot-fixes` | HEAD `fcac4469`; pushed; only unrelated CSV deletion |
| `platform-student-py3` | `student-py3-analysis` | #2357 |
| `platform-courseware-py3` | `courseware-py3` | #2359 |
| `platform-instructor-py3` | `instructor-py3` | #2360 |
| `platform-contentstore-py3` | `contentstore-py3` | #2361 |
| `platform-phase5-6d-apis` | `phase5-6d-apis` | #2362 |
| `platform-phase5-6b-core` | `phase5-6b-core` | #2363 |
| `platform-phase5-6c-libs` | `phase5-6c-libs` | #2364 |
| `platform-phase5-6a-xmodule` | `phase5-6a-xmodule` | #2365 |
| `platform-py3-integration` | `py3-integration` | Merged all 8 |

## Key Docs

| Path | Content |
|------|---------|
| `devstack/docs/progress-plan-20260724.md` | Latest progress table |
| `devstack/docs/django-boot-fixes-20260723.md` | Boot fix catalog |
| `devstack/docs/py36-probe-result-20260723.md` | Python 3.6 probe evidence |
| `devstack/docs/dependency-bridge-analysis.md` | Dependency upgrade plan |
| `devstack/docs/juniper-dependency-comparison.md` | Juniper vs our deps |
| `devstack/docs/oep-0007-comparison.md` | OEP-7 compliance |
| `devstack/docs/py36-image.md` | Image documentation |
| `devstack/docker/py36/BUILD.md` | Image build script |
| `devstack/docs/execution-review-*.md` | Review rounds 1-26 (historical checkpoints) |

## Reproducibility notes

- The running container bind-mounts host `platform/` at `/edx/app/edxapp/edx-platform`; `docker exec` source edits change the host worktree directly.
- The Py3 image pins are sourced from `devstack/docker/py36/py36-base.txt` and the image Dockerfile. The legacy `platform/requirements/edx/py36-base.txt` still contains the Py2-era dependency set; do not use it as the source for reproducing this Py3.6 container.
- Verified versions in `py36-build`: Django 1.11.29, DRF 3.11.2, Celery 3.1.25, Kombu 3.0.37.

## Next action

The XML/content-store path is isolated and targeted-verified. The 55-file batch is committed at `9e1bd6f86a3`; the current follow-up is committed and pushed at `fcac4469cf7`. Resolve or explicitly provision the remaining container dependency/pytest collection blockers, then drive the `720–722` runtime failures and `81` collection errors separately. Keep the baseline range unchanged until a fresh canonical run completes. Continue to isolate `SiteConfigurationTests.test_get_all_orgs` separately. Do not stage the unrelated CSV.

## 2026-07-28 execution continuation after R27

- **New source commit:** `4661df6190f` (`fix(py3): unblock API and Mongo runtime paths`), 17 Python files, 57 insertions / 33 deletions. This commit is not yet pushed; it does not include the unrelated deleted survey CSV.
- The batch restores the real `JwtAuthentication` imports and DRF `action` routes, completes PyMongo 3 client handling, fixes transcript text/bytes input, safe-session hashing, and Python 3 codec paths. `six.viewkeys()` now supports the split Mongo bulk-write cleanup on both Python 2 and Python 3.
- Course-run targeted result after the two follow-up fixes: **16 passed / 2 failed**. Both remaining failures are `test_rerun` and are downstream of the installed `edxval==0.1.16` package: `edxval.api.copy_course_videos()` raises `NameError: unicode is not defined`. The create pair is **2/2 passed** after opening the default JPEG in `rb` mode.
- Modified-source `compileall` and `git diff --check` pass. A fresh LMS boot check is currently blocked by the dependency combination: `edx-when==1.3.2` imports `edx_rest_framework_extensions.auth`, while installed `edx-drf-extensions==1.5.2` exposes `authentication.py` and no `auth` package. Do not claim the previous 0-issue boot result for this dependency state.
- No new full-suite run was completed; retain the historical `720–722 / 1445–1447 / 586` and canonical `12464 collected / 81 errors` figures unchanged.

### Review handoff at `4661df6190f`

1. Review the 17-file commit, especially `cms/djangoapps/contentstore/views/course.py:909`, `common/lib/xmodule/xmodule/modulestore/split_mongo/split.py:249,260`, JWT imports, and PyMongo fallbacks.
2. Resolve or provision a Python 3-compatible `edxval` before rerunning the two rerun tests; assess an `edxval` 4.x upgrade against this Hawthorn API rather than swallowing `copy_course_videos` errors.
3. Align `edx-when` with `edx-drf-extensions` (or provide a justified compatibility pin), then rerun LMS/CMS boot checks.
4. Keep the CSV deletion untouched and keep collection, runtime, and external dependency failures as separate queues.
