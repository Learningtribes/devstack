# E6 discussion XBlock image fix and re-gates (2026-10-10)

## Why

The first E6 discussion provision attempt (`../e6-gates/discussion-py36/attempt1/`)
failed with `PluginMissingError: discussion`. The Py3.6 runtime image never
installed the in-tree `openedx/core/lib/xblock_builtin/xblock_discussion`
distribution, so the `xblock.v1` entry point `discussion` did not exist. The
Py2.7 image installs it from `requirements/edx/local.in`. The Dockerfile now
installs that distribution's metadata with `--no-deps`; the runner's
source-first `PYTHONPATH` still loads the module from the mounted platform tree.

## Image

| Item | Value |
| --- | --- |
| Runtime | `ltdps/edxapp:py36-r2-20261009` = `sha256:f02cf5e79316295694dff8e5248b8704fcd1866fb8b651bef9384c7b395aec37` |
| Previous runtime | `sha256:9b43579930c4...`, tagged `py36-r2-20261009-pre-discussion` |
| Layers | 29; first 25 shared with the previous image (`old-layers.txt`, `new-layers.txt`) |
| Freeze diff | `+xblock-discussion==0.1` only (`e2-rebuild/freeze-diff-vs-pre-discussion.txt`) |
| Py3.6 test runner | `sha256:004a03ddbb81cb7866028f1b4c7233242e39668c529e8022daa5e8798ac3863b` (`runners/`) |
| Py2.7 test runner | unchanged |

## Re-gates on the new image

| Gate | Result | Evidence |
| --- | --- | --- |
| E2 | `pip check` clean; compile path set unchanged; `xmodule.v1` 35/0; `xblock.v1` 48 with `discussion=xblock_discussion.DiscussionXBlock`; the LMS `scormxblock` failure is pre-existing | `e2-rebuild/` |
| E3 | LMS check exit 0 with the two known `urls.W005`; CMS no issues; import smoke 122/122 and 7/7, identical | `e3-rebuild/` |
| E4 | Full pass; HTTP gate equal modulo body size; course payload equal; tasks unchanged | `e4-rebuild/` |
| E5 py36 | 118/109/38 passed; r2-dcc 85 failed / 274 passed / 13 skipped / 2 errors; progress strings, node sets and classifier output byte-identical to the previous image | `final/` |
| E6 assets | Recollected into `/tmp/py36-r2-e6-assets-20261010-r4`; 0 differing entries against r3 for both runtimes | provenance in the asset root |

## E6 group 1 rerun (private, isolated, cloned Elasticsearch, no forum)

The earlier group 1 run was invalid: its "private" Elasticsearch had joined the
shared cluster through multicast discovery (see
`../e6-private/es-shared-cluster-incident/`). The rerun uses a single-node
private cluster (`es_isolated cluster=py36-r2-e6-<rt>-es nodes=1`) restored from
a GET-only snapshot of the shared indices (`r2-e6-es-clone.py`). The two red
shared indices have no readable primaries, so they are cloned with their
mappings only.

| Runtime | Result | Failures | Service logs |
| --- | --- | --- | --- |
| py36 | 27/30 | p1b-dashboard last-activity x2, pr-2396 chooser 404 (accepted) | one INFO cohort-cache line, no 5xx |
| py27 | 27/30 | same three | same INFO line, no 5xx |

With the cloned indices, Studio `/program_search/` and `/course_search/` no
longer return 500, and the earlier CMS `fa-regular-400.woff2` 500 does not
recur.
