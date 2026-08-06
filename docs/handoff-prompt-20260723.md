## Py3.6 Migration — Current Handoff

> Status: HISTORICAL HANDOFF
>
> Current cross-repository state and assignments live in the
> [migration Hub](https://github.com/Learningtribes/platform/tree/migration_discussion/docs/migration_discussion).
> This file preserves the R27 handoff observed at the identity below.
>
> Historical snapshot: 2026-07-28 · former canonical status: `progress-plan-20260724.md` · HEAD: `fcac4469cf7`
>
> Older R20 figures, “push 6 commits” instructions, and the R27 next-action
> section are evidence of that session rather than current instructions.

### Historical one-line status

**720–722 failed / 1445–1447 passed / 84 skipped / 586 errors** on Py3.6. Latest canonical `--tb=line`: **720 failed / 1447 passed**. The canonical collection-only run is **12464 collected / 81 errors**. This is a 52.5% pass rate and **+626 passed tests vs R18**. Django booted; broad boot blockers are addressed, but repository-wide Py2 residue remains. The 55-file batch used for this measurement is committed as `9e1bd6f86a3`; the 41-file follow-up is committed and pushed as `fcac4469cf7`. No new full-suite totals are claimed for the follow-up because its full run stopped at 80% after 21 minutes without progress.

### Entry doc

`/Users/noahwang/workspace/hawthorn/devstack/docs/progress-plan-20260724.md` — full progress table + worktree map + doc index.

### What works

- `django.setup()` + `call_command("check")` → 0 issues
- 7 pip pins locked: Django 1.11.29 / celery 3.1.25 / kombu 3.0.37 / pymongo 3.9.0 / mongoengine 0.10.0 / mysqlclient 1.4.6 / DRF 3.11.2
- Container: `ltdps/edxapp:py36`, `py36-build` running; host `platform/` is bind-mounted
- Branch: `py36-boot-fixes`, HEAD `fcac4469cf7`, already pushed (`origin/...HEAD = 0/0`), 25 commits ahead of `origin/master`
- Worktree warning: only one unrelated CSV is deleted; do not stage, restore, or commit it

### Current working-tree follow-up

The committed 55-file source batch touches xmodule/CAPA, memcache, LTI, grades, and graph traversal paths. It fixes the observed `six` `NameError`s, iterator `.next()`, CAPA/safe-exec/grades hash and text handling, `dict_keys` indexing, XML/HTML bytes boundaries, LTI body hashing, WebOb bytes/text handling, deterministic video export, the bad lxml encoding literal introduced by the broad `unicode` replacement, and the CAPA checker collection blocker. The commit is `9e1bd6f86a3`; it only records the already-measured working-tree state. The broader run remains blocked by codejail/pysrt and test-collection compatibility; the Mongo/XML wait is isolated and targeted-verified, so do not update the full-suite totals yet.

The follow-up commit `fcac4469cf7` fixes another 41-file Py3 batch: legacy imports/stdlib codecs, test bytes/text boundaries, the callable legacy nose `attr` shim, and verify_student/shared base64 paths. `ssencrypt.py` now uses byte AES IVs, an explicit bytes RSA plaintext contract, text signatures, and text canonical signing payloads. `verify_student/models.py`, `verify_student/image.py`, and `common/djangoapps/util/models.py` use explicit base64/`BytesIO` APIs. Targeted encryption/signing tests pass **5/5**, the image/compressed-text codec smoke passes, modified files compile, and Django `check` is 0 issues.

### 2026-07-28 continuation

The Mongo/XML follow-up is now on disk and verified. `MongoContentStore` handles PyMongo 3 clients, database drops, GridFS bytes/text/file streams, aggregate cursors, and `UpdateResult` results while retaining legacy PyMongo fallbacks. Mongo traversal now handles `depth=None`, and `CourseAssetsFromStorage` exposes `.items()`. The XML unicode test reads binary fixture data.

With `EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo`, `test_contentstore.py` passed 14/14, `test_mongo.py` 54/54, and `test_xml_importer.py` 7/7. The combined XML/Mongo/contentstore run passed 80 tests after excluding only `test_dag_course`. `test_xml.py` itself passed 5 tests; its DAG test is blocked because the container has no installed `discussion` XBlock (the repository source also requires missing `xblockutils`). `test_asset_xml.py` remains a collection blocker caused by the legacy nose `attr` decorator resolving to pytest's non-callable `MarkGenerator`. Mongo is not an active blocker when the service hostname is supplied. The full-suite baseline remains unchanged.

### Review-agent handoff (2026-07-28)

Review commits `9e1bd6f86a3` and `fcac4469cf7` at HEAD on `py36-boot-fixes`. The branch is already pushed and is 25 commits ahead of `origin/master`; do not push again unless `git rev-list origin/py36-boot-fixes..HEAD` is non-empty. Treat the deleted survey CSV as unrelated: do not stage, restore, commit, or push it. Do not reset or discard any existing working-tree change. Review `fcac4469cf7` first, especially the bytes/text and base64 changes in verify_student and `common/djangoapps/util/models.py`, then continue the existing Mongo/XML and xmodule/CAPA/LTI/grades/graph review.

Required evidence is the targeted command below with `EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo`, plus the boot check and `git diff --check`. Do not treat the historical full-suite `720–722 / 1445–1447 / 586` figures as newly verified. Report findings by severity with file/line references. The known environment blockers are missing `discussion` XBlock/`xblockutils`, the legacy nose `attr`/pytest `MarkGenerator` collection failure, external codejail `long`, and pinned pysrt Python-2 builtins.

Independent read-only review result: **APPROVE for handoff**, with no Critical or Major findings. Minor follow-ups are `video_module.py:994-1001` (narrow the broad `NameError` compatibility catch when this batch is revisited) and `capa/tests/test_inputtypes.py:748-753` (replace self-derived expected values with assertions on key rendered fields). These do not block the current handoff.

### What's left

1. Resolve or provision the remaining codejail/pysrt/discussion-XBlock and pytest-nose collection blockers in `py36-build`; the Mongo host issue is isolated and targeted tests are green. Do not change the baseline totals from focused tests alone
2. Isolate the 720–722 one/two-test baseline swing (`SiteConfigurationTests.test_get_all_orgs`)
3. Use the R33 collection list: CMS-only settings/app-label failures, missing `pyquery`/`urlparse`/`openpyxl`/`before_after`/`pygeoip` dependencies, Python-2-only lettuce and edx-oauth2-provider code, and the deferred coursegraph/discussion/enterprise stubs; keep these separate from runtime failures
4. ORA2/openassessment + 6F (~70K SLOC) deferred runtime risk
5. Four prod-gate classes: SAML, coursegraph, enterprise, JWT
6. DCC merge + Phase 4/5 rebase (external status must be refreshed)

### Key commands

```bash
# Container
docker exec -it py36-build bash

# Mongo-backed targeted regression
docker exec py36-build bash -c 'cd /edx/app/edxapp/edx-platform && \
  EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo DJANGO_SETTINGS_MODULE=lms.envs.test \
  python3 -m pytest --tb=line --disable-warnings -q \
  -k "not test_dag_course" \
  common/lib/xmodule/xmodule/modulestore/tests/test_contentstore.py \
  common/lib/xmodule/xmodule/modulestore/tests/test_xml.py \
  common/lib/xmodule/xmodule/modulestore/tests/test_mongo.py \
  common/lib/xmodule/xmodule/modulestore/tests/test_xml_importer.py'

# Boot check
docker exec py36-build bash -c 'cd /edx/app/edxapp/edx-platform && DJANGO_SETTINGS_MODULE=lms.envs.test python3 -c "import django; django.setup(); from django.core.management import call_command; call_command(\"check\"); print(\"BOOT OK\")"'

# Baseline (8 min)
docker exec py36-build bash -c 'cd /edx/app/edxapp/edx-platform && DJANGO_SETTINGS_MODULE=lms.envs.test python3 -m pytest --ignore=src --ignore=pavelib --ignore=scripts --continue-on-collection-errors --tb=no -q'
```

### First action for the next execution agent

```bash
docker exec py36-build bash -c 'cd /edx/app/edxapp/edx-platform && \
  DJANGO_SETTINGS_MODULE=lms.envs.test python3 -m pytest \
  --ignore=src --ignore=pavelib --ignore=scripts \
  --continue-on-collection-errors --tb=line -q 2>&1' > /tmp/tbline-current.txt
```

The historical canonical run currently ends at `720 failed / 1447 passed / 84 skipped / 586 errors`; repeated runs vary by one or two tests. R33 collection-only is `12464 collected / 81 errors`. No new full-suite total is claimed from the stopped follow-up run. The XML/content-store path is targeted-verified with the Mongo hostname override; provision the remaining dependency and collection blockers before the next baseline. Isolate `SiteConfigurationTests.test_get_all_orgs` before treating the one-test swing as progress. Classify collection errors separately from runtime `F` results. The latest source commit is `4661df6190f` (not yet pushed); verify `git rev-list origin/py36-boot-fixes..HEAD` before any push. After each source batch, run the boot check and record the exact HEAD and full-run totals.

## Immediate handoff update — 2026-07-28 after R27

### Source state

- HEAD: `4661df6190f`, one new local commit after `fcac4469cf7`; the commit contains 17 Python files and no CSV.
- The worktree's deleted survey CSV is unrelated and must remain unstaged, un-restored, and uncommitted.
- `compileall` for all modified Python files and `git diff --check` passed.

### Latest focused evidence

- `cms/djangoapps/api/v1/tests/test_views/test_course_runs.py`: **16 passed / 2 failed** with `EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo`.
- Both create parameterizations pass after `cms/djangoapps/contentstore/views/course.py` opens `triboo_default_image.jpg` with `rb`; the previous `0xff` decode was a Python 3 text-mode file bug.
- The split Mongo `dict.viewkeys()` failures were corrected with `six.viewkeys()`. The remaining two rerun failures now reach the external `edxval.api.copy_course_videos()` call and fail at installed `edxval==0.1.16` with `NameError: unicode is not defined`.
- A fresh LMS boot check is not green in this exact dependency state: installed `edx-when==1.3.2` imports `edx_rest_framework_extensions.auth`, but `edx-drf-extensions==1.5.2` only exposes `edx_rest_framework_extensions.authentication`. Treat this as a dependency bridge blocker, not as a reason to revert the real JWT imports without review.

### Next agent commands

```bash
# Review the local commit and preserve the CSV state.
git show --stat --oneline 4661df6190f
git status --short

# Reproduce the remaining focused failures with task logs.
docker exec py36-build bash -lc 'cd /edx/app/edxapp/edx-platform && \
  EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo DJANGO_SETTINGS_MODULE=cms.envs.test \
  python3 -m pytest --tb=long --log-cli-level=ERROR --disable-warnings -q \
  cms/djangoapps/api/v1/tests/test_views/test_course_runs.py -k "test_rerun"'
```

Resolve/provision compatible `edxval` and align `edx-when` with the DRF extension namespace before refreshing boot or full-suite totals. Do not silently catch the external `copy_course_videos` failure, do not update the historical baseline from this focused run, and keep ORA2/6F and the 81 collection errors in their separate queues.
