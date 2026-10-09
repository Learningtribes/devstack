# E5 - DCC/R2 regression targets on both runtimes (2026-10-09)

Source: `platform-r2-py36-src` detached at PR #2401 head
`0ac3bfa6d099916cc58fc258db17221801f49d48` (tree `357effc3232a`), clean,
mounted read-only. Mongo prefixes `py36-r2-e5-py36` / `py36-r2-e5-py27`.

## Runners

| Runner | Image ID | Arch | Base | Layer prefix |
| --- | --- | --- | --- | --- |
| `ltdps/edxapp:py36-r2-py36-runner-20261009` | `sha256:cba96e85d6e5` | arm64 | `py36-r2-20261009` = `sha256:4560a9c2b264` | 25/31 OK |
| `ltdps/edxapp:py36-r2-py27-runner-20261009` | `sha256:e5ecccf98eb9` | amd64 | `m5-fixed` = `sha256:50b4a73f4814` | 14/21 OK |

BuildKit (orbstack, containerd store) cannot resolve `FROM <tag>@sha256` for the
never-pushed Py3.6 runtime, so the Dockerfile uses the local tag and
`r2-build-test-runners.sh` proves the runner RootFS starts with every base
layer (`build/runner-identity.txt`). Runner additions: test tools only
(`testfixtures==6.2.0` added to the Py3.6 tool lock; Py2.7 adds edx-search
`c770553b`). Neither image was pushed.

`final/identity-py{36,27}.txt`: `django.setup()` OK on both runtimes, exactly one
`edx_proctoring` app with the overlay append removed (closes the E2 open
finding), django-wiki 0.0.27 on Py3.6 and 0.0.18 on Py2.7.

Test overlay change: `xblock_config` is no longer injected into the LMS profile;
its `ready()` replaces xmodule's global `handler_url` with Studio's and broke Py2.7
completion handler tests.

## Results

Node lists are normalized for ddt Py2/Py3 naming with `normalize_nodes.py`.

| Target | Py3.6 collect | Py2.7 collect | Py3.6 exec | Py2.7 exec |
| --- | --- | --- | --- | --- |
| focused (control) | 118 | 118, identical | 118 passed | 118 passed |
| p1b-batch1 (control) | 109 | 109, identical | 109 passed | 109 passed |
| p1b-batch2 (control) | 38 | 38, identical | 38 passed | 38 passed |
| r2-dcc (11 files) | 372 + 2 collection errors | 643 | 88 failed / 271 passed / 13 skipped / 2 errors | 3 failed / 507 passed / 133 skipped |

r2-dcc collection: the two Py3.6 collection errors are master Py3 gaps already in
the E3 accepted syntax-error set: `courseware/tests/test_views.py:10`
(`from HTMLParser import HTMLParser`, 218 Py2.7 nodes) and
`openedx/core/djangoapps/theming/tests/test_util.py:68` (print statement, imported
by `student_account/test/test_views.py`, 53 Py2.7 nodes). Excluding those two
files, the normalized node sets are identical (`final/r2-dcc-nodes-norm-diff.txt`
empty; 372 + 218 + 53 = 643).

## Failure classification

`classify_failures.py` takes the deepest platform frame of each failure and checks
whether that source line exists verbatim at master `6750b533`.

Py3.6 (`final/r2-dcc-classify-py36.txt`): 90 sections, every failing line exists on
master, 0 lines introduced by R2. No DCC/R2 regression.

| Count | Cause | Layer |
| --- | --- | --- |
| 32 | `student/tests/factories.py:135` pops kwargs while iterating `keys()` | test code, Py3 gap |
| 23 | `unicode` builtin | test code, Py3 gap |
| 13 | bytes vs str on `response.content` | test code, Py3 gap |
| 4 | discussion views HTTP 500: `django_comment_client/utils.py:293` sorts `None` `sort_key` | product, master Py3 defect |
| 3 | `comment_client/utils.py:98` compares `MagicMock` with int (ForumDiscussionXSS) | test mock, Py3 gap |
| 4 | certificate grade ddt compares `None` with float | test code, Py3 gap |
| 3 | `course_modes` `create_mode` passes GET string `min_price`; `models.py:200` `str <= int` | product test-only view, master Py3 defect |
| 3 | django-wiki 0.0.27 urlize needs Markdown 2 API (`markdown_instance`) | Py3.6 lock defect (Markdown 3.3.7) |
| 2 | `xrange` | test code, Py3 gap |
| 1 | `basestring` | test code, Py3 gap |
| 2 | collection errors above | test code, Py3 gap |

dogapi statsd bytes errors appear in logs only and fail no test.

Py2.7 (`final/r2-dcc-classify-py27.txt`): 3 `TestJumpTo` failures, environment
only. The mixed XML modulestore uses `fs_root=common/test/data` and opens OSFS with
`create=True`, which cannot write into the read-only source mount.

## Markdown probe

`probe-markdown-2611.sh` reran r2-dcc on the unchanged Py3.6 runner with
Markdown 2.6.11 (Platform `requirements/edx/base.txt:165`) installed into the
runner tmpfs and first on `PYTHONPATH` (`final/probe-markdown-2611.txt`):
85 failed / 274 passed / 13 skipped / 2 errors. Exactly the three
`WikiRedirectTestCase` failures were fixed and no failure was added.

The Py3.6 lock pins `Markdown==3.3.7` (`py36-base.txt`, `py36-constraints.txt`,
inherited from R1). django-wiki 0.0.27 and Platform `mdx_mathjax.py` /
`mdx_video.py` use the Markdown 2 extension API; xblock-poll 1.5.1 accepts
`>=2.6.11,<3.4`. The owning fix is `Markdown==2.6.11` in the Py3.6 lock plus a
runtime image rebuild, which changes the E2-E4 image identity.

## Verdict

E5 PASS for the R2 question: no DCC/R2-introduced failure on either runtime,
controls identical and green, collection identical outside two accepted master
Py3 gaps. Open findings: Markdown lock defect (owner decision on rebuild), two
master Py3 product defects (`django_comment_client` sort, `course_modes`
`create_mode`), and the test-code Py3 gaps, all outside the R2 delta.
