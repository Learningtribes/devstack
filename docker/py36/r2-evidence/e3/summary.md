# E3 static runtime gates: PASS

Completed 2026-10-09 20:40 +0800.

| Input | Value |
|---|---|
| Image | `ltdps/edxapp:py36-r2-20261009` (`sha256:4560a9c2b264…`), unchanged since E2 |
| Source | `platform-r2-py36-src` detached at `0ac3bfa6d09` (read-only mount) |
| Source delta vs `fd5e359ec1c` | one local commit on branch `r2-py36-runtime-fixes` (not pushed): `0001-fix-py36-restore-dual-runtime-settings.patch`; `setup.py` unchanged, so the image's installed Platform metadata still matches |
| Config | `.py36-r2-config/{lms,cms}.{auth,env}.json` (copied from `edx.devstack.lms` / `edx.devstack.studio`, mode 600, not committed) |
| Runner | `r2-e3-run.sh` (`docker run --rm`, label `io.openedx.py36-r2.gate=e3-check`, network `devstack_default`) |

## Why the source changed

`fd5e359ec1c` failed both checks (`lms-check-attempt1.txt`,
`cms-check-attempt1.txt`). Root cause and diagnosis:
`finding-r1-lost-settings-fixes.md`. With the user's go-ahead (local fix
branch, no push), `0ac3bfa6d09` restores the five lost R1 fixes in a
dual-runtime form:

| Fix | Python 2.7 form vs R1 form |
|---|---|
| `plugin_apps.get_apps(project_type, installed_apps)` skips plugins already in `INSTALLED_APPS`; LMS/CMS pass `INSTALLED_APPS` | R1 deleted the static `edx_proctoring` entries, which would unregister the Python 2.7 fork (1.4.0, no entry point). Both versions use `default_app_config = EdxProctoringConfig`, so the result is the same AppConfig on both runtimes |
| CMS imports `HEARTBEAT_ELASTICSEARCH_TIMEOUT` | same as R1; R2-preview's CMS also failed on Python 2.7 without it |
| `MIGRATION_MODULES['submissions']` in LMS/CMS | same as R1; snapshots equal edx-submissions 2.0.12 and 2.1.1 except byte literals (`dual-runtime-dependency-comparison.txt`) |
| Wiki include uses `wiki_pattern()[:2]` | R1 used 2-tuple unpacking, which fails on django-wiki v0.0.18's 3-tuple |

## Gates

| Gate | Result | Evidence |
|---|---|---|
| LMS `check --settings=devstack_docker` | exit 0; only the two known `urls.W005` `edx_proctoring` warnings | `lms-check-final.txt` |
| CMS `check --settings=devstack_docker` | exit 0; no issues | `cms-check-final.txt` |
| Platform compile, Python 3.6 (all 3,192 tracked `.py`) | 29 syntax errors, 24 warnings — identical error set to R1 HEAD `33590b3ab47` (29); master `6750b533180` has 31; 0 new. All are Python 2-only tests, acceptance pages, `scripts/`, `common/lib/sandbox-packages/eia.py`, `openedx/core/lib/rsa_key_utils.py` (Phase 5 residue, not R2 regressions) | `compile-py36-*.txt`, `e3_compile.py` |
| Import smoke: 129 non-test modules added/modified by `fd5e359ec1c` + `0ac3bfa6d09` | LMS 122/122, CMS 7/7 | `import-smoke-*.txt`, `import-smoke-files.txt`, `e3_import_smoke.py` |

## Fix verification

| Check | Python 3.6 | Python 2.7 |
|---|---|---|
| `test_plugin_apps` (3 tests) | OK (`fix-unit-py36.txt`) | OK (`fix-unit-py27.txt`, `m5-fixed`) |
| Runtime probe (`probe_runtime_fixes.py`) | one `edx_proctoring`; submissions from snapshots; heartbeat 2; `wiki` and `course_wiki_do_not_reverse` namespaces, `/wiki/` reverses | identical (`py27-fix-*-probe.txt`) |
| LMS / CMS check | exit 0 / exit 0 | exit 0 / exit 0 (`py27-fix-*-check.txt`); baseline `fd5e359ec1c`: LMS exit 0, CMS `NameError` (`py27-base-*`) |

Python 2.7 runs used image `r2-preview-studio:20261009` (the R2-preview
Python 2.7 runtime), `edx-search` mounted read-only, and an untracked copy
of `Open_edX.egg-info` (entry points identical to the Python 3.6 image's
installed metadata). Deviation: the Python 2.7 *baseline* mounted
`platform-r2-preview` read-only in a disposable container (plan §4 says not
to mount it; handoff §6 allows Python 2.7 spot checks). No file or container
was modified.

## Residual (not E3 failures)

- `urls.W005` duplicate `edx_proctoring` URL namespace on Python 3.6:
  `lms/urls.py` includes the proctoring URLs statically and the 1.5.7
  plugin adds them again. Accepted by the R1 pass criterion.
