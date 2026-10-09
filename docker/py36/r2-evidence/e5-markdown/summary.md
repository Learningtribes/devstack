# E5 follow-up - Markdown 2.6.11 lock fix and identity re-gates (2026-10-09)

Owner decision (2026-10-09): fix the Python 3.6 lock, rebuild the runtime, and
re-run the identity-sensitive gates. Master Python 3 defects found in E5 go to
master owner PRs / Track E, not PR #2401.

## Lock and image

| Item | Value |
| --- | --- |
| Lock commit | `51fe2d8` - `Markdown==3.3.7` -> `Markdown==2.6.11` in `py36-base.txt` and `py36-constraints.txt` (nothing else; `importlib-metadata` stays for `click`) |
| Build | R1 `build_command`, no-cache, `DEBIAN_SECURITY_MIRROR=http://archive.debian.org/debian-security` (as E2), Platform context `platform-r2-py36-src` @ `0ac3bfa6d09` (the eight metadata files copied by the Dockerfile are identical to `fd5e359ec1c`), 20:59-21:15, exit 0, 2x `Image build OK` + 2x `XModule entry points OK` |
| New runtime | `ltdps/edxapp:py36-r2-20261009` = `sha256:8c2e7df2e03d5155be22b6bb70d885a9f88987ff1f74f7ac6a2d1b31165d0355` (arm64, local only) |
| Previous runtime | `sha256:4560a9c2b264` kept as `ltdps/edxapp:py36-r2-20261009-markdown337` |
| Py3.6 runner | `ltdps/edxapp:py36-r2-py36-runner-20261009` = `sha256:e36ae142a1dc` (base layer prefix 25/31 OK) |
| Py2.7 runner | unchanged, `sha256:e5ecccf98eb9`; its E5 results stand |

Scripts that pin the runtime ID now name `sha256:8c2e7df2e03d`
(`run-r2-e4-services.sh`, `r2-build-test-runners.sh`,
`Dockerfile.r2-py36-test-runner`). `r2-build-test-runners.sh` takes an optional
`py36|py27|all` selector so the Py2.7 runner is not rebuilt needlessly.

## Gates

| Gate | Result | Evidence |
| --- | --- | --- |
| E2 `pip check` | No broken requirements | `e2-rebuild/pip-check.txt` |
| E2 freeze | 221 lines; vs E2 freeze (case-insensitive sort) exactly `Markdown 3.3.7 -> 2.6.11` | `e2-rebuild/freeze-diff-vs-e2.txt` |
| E2 site-packages compile | same 3 accepted paths, path-set sha256 `cc0d80d8...` (= E2 = R1) | `e2-rebuild/site-packages-compile*.txt` |
| E2 entry points | plain `lms.envs.test` and `cms.envs.test` (no probe settings; `0ac3bfa6d09` fixed the duplicate label): one `edx_proctoring`, `xmodule.v1` 35 / 0 failures, course=`CourseDescriptor`, hidden=`HiddenDescriptor`, course tools bookmarks/reviews/updates; django-wiki urlize + `mdx_mathjax` + `mdx_video` render on Markdown 2.6.11 | `e2-rebuild/entry-points.txt`, `e2-recheck.sh` |
| E3 LMS `check --settings=devstack_docker` | exit 0, only the two known `urls.W005` proctoring warnings; three Markdown 3 import-time DeprecationWarnings from the E3 run are gone | `e3-rebuild/lms-check.txt` |
| E3 CMS check | exit 0, no issues | `e3-rebuild/cms-check.txt` |
| E3 import smoke | LMS 122/122, CMS 7/7 | `e3-rebuild/import-smoke-*.txt`, `e3-recheck.sh` |
| E3 Platform compile | not re-run: depends only on source and interpreter, both unchanged | - |
| E4 services (`e4/r2-e4-run.sh`, window 13:18:07Z-13:19:06Z) | all 8 HTTP checks as E4 (CMS authenticated `/` 200, static 200, heartbeats 200); course read LMS 1/6 blocks, CMS 1/1; tasks SUCCESS/SUCCESS/FAILURE(controlled)/SUCCESS; warm shutdown exit 0 in 3 s; post-restart SUCCESS x2; `py36-r2.lms.default` 0/0/1; logs 0 Traceback/import/XBlock/5xx except the controlled failure | `e4-rebuild/` (Set-Cookie values redacted, HTML/JS bodies dropped as in E4) |
| E5 Py3.6 identity | `django_setup=ok`, one `edx_proctoring`, django-wiki 0.0.27 | `final/identity-py36.txt` |
| E5 Py3.6 controls | focused 118, p1b-batch1 109, p1b-batch2 38 passed; node lists identical to E5 | `final/*-py36.txt` |
| E5 Py3.6 r2-dcc | 85 failed / 274 passed / 13 skipped / 2 collection errors; node list identical to E5; failure set = E5 minus exactly the 3 `WikiRedirectTestCase` tests = the tmpfs probe result; classifier: 87 sections, all master lines, 0 R2 lines | `final/r2-dcc-*.txt` |

## Verdict

Markdown lock defect fixed in the owning layer (the Py3.6 lock). The rebuilt
runtime passes every identity-sensitive E2-E5 gate with no new difference
beyond the intended Markdown line. Remaining Py3.6 failures are the master Py3
gaps recorded in `../e5/summary.md` (owner: master PRs / Track E).
