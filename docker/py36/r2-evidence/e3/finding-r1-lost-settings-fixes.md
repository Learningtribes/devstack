# E3 finding: R1 runtime fixes lost after the R1 master syncs

Observed 2026-10-09 19:40 +0800. Image `ltdps/edxapp:py36-r2-20261009`
(`sha256:4560a9c2b264…`), source `fd5e359ec1c` read-only, LMS/CMS JSON
copied from `edx.devstack.lms` / `edx.devstack.studio` (mode 600, not
committed), `--settings=devstack_docker`, network `devstack_default`.

## Result on R2-preview as-is

| Service | Exit | First error |
|---|---|---|
| LMS check | 1 | `ImproperlyConfigured: Application labels aren't unique, duplicates: edx_proctoring` (`lms-check-attempt1.txt`) |
| CMS check | 1 | `NameError: HEARTBEAT_ELASTICSEARCH_TIMEOUT` at `cms/envs/aws.py:280` (`cms-check-attempt1.txt`) |

This supersedes the E2 hypothesis: the duplicate is not test-settings-only.

## Root cause

R1 carried five Python 3.6 runtime fixes that R1 HEAD `33590b3ab47` (the
source of R2-preview's code delta `fd5e359ec1c`) no longer contains:

| # | R1 fix | Lost in | Python 2.7 coupling |
|---|---|---|---|
| 1 | `c2e17490d5c` drop LMS `OPTIONAL_APPS` `('edx_proctoring', None)` | `04af2db3d04` Merge origin/master (2026-09-21) | Py3 lock `edx-proctoring==1.5.7` registers `EdxProctoringConfig` via `lms/cms.djangoapp`; Py2 `m5-fixed` carries 1.4 without that entry point (R1 runner overlay re-adds the app on Py2). Plain removal would unregister proctoring on Py2/production (`ENABLE_SPECIAL_EXAMS=True`) |
| 2 | `e997918605a` drop CMS `INSTALLED_APPS` `'edx_proctoring'` | same merge | same as 1 |
| 3 | `43d2b8feb77` CMS import `HEARTBEAT_ELASTICSEARCH_TIMEOUT` from `lms.envs.common` (the `cms/envs/aws.py` consumer survived) | same merge | none; consumer line exists only on R1/R2 |
| 4 | `MIGRATION_MODULES = {'submissions': 'openedx.core.djangoapps.submissions_migrations'}` in LMS and CMS (package still present, now unwired) | same merge | snapshots are dual-runtime by design; Py2 behavior to confirm |
| 5 | `18ecff95a74` course wiki `include((wiki_url_patterns, ...), namespace=...)` | `4dbe0c68497` "Fix Python 2.7 LMS and CMS unit failures" (2026-09-28) reverted it to `wiki_pattern(app_name=..., namespace=...)` | Py3 lock `django-wiki@4ceac471` `get_pattern(app_name)` has no `namespace`; the Py2 runtime's wiki accepts it. Genuine dual-runtime dependency drift |

`r1-merge-lost-line-scan.py` (output `r1-merge-04af2db3d04-lost-line-scan.txt`)
lists every R1-added line absent after `04af2db3d04`. Items 1–4 are the only
ones still wrong on R2-preview; the rest were re-fixed later on R1 or are
legitimately superseded by master dead-code removals (teams, entitlements,
external_auth, badges, support). The scan covers the merge only, so item 5
(a later ordinary commit) was found by the check, not the scan.

## Diagnosis proof (temporary copy, no worktree edited)

`git archive fd5e359ec1c` into `/tmp/r2-e3-diag-src` plus
`diagnosis-restore-r1-fixes.patch` (items 1–5 in their R1 form):

| Service | Exit | Output |
|---|---|---|
| CMS check | 0 | `System check identified no issues (0 silenced).` |
| LMS check | 0 | only the two known `urls.W005` `edx_proctoring` namespace warnings (R1 pass criterion) |

The R1 form of items 1, 2 and 5 is Python-3-only; it is diagnosis, not a
deliverable fix.
