# Py3.6 Image Build & Run Guide

> **Superseded as a reproducible build contract:** this guide describes the original probe bootstrap. The running container has drifted from these inputs. Use the active [integration plan](../../../platform/docs/plans/py36-integration-probe-plan-20260728.md) and [runtime evidence](../../../platform/docs/plans/py36-integration-evidence.md). Do not treat a successful interactive bootstrap as a locked image.

## Build

```bash
cd /Users/noahwang/workspace/hawthorn/devstack/docker/py36
docker build -t ltdps/edxapp:py36 .
```

## Test (interactive)

```bash
docker run --rm -it \
  -v /Users/noahwang/workspace/hawthorn/platform:/edx/app/edxapp/edx-platform \
  --network devstack_default \
  ltdps/edxapp:py36 bash
```

## Verify

```bash
# Bootstrap environment
docker exec <container> bash -c '
  cd /edx/app/edxapp/edx-platform
  pip install -e common/lib/xmodule
  pip install -e common/lib/capa
  pip install -e common/lib/calc
  pip install -e common/lib/symmath
  pip install -e common/lib/safe_lxml
  pip install -e common/lib/chem
  pip install -e common/lib/sandbox-packages
  pip install -e common/lib/dogstats
  pip install -e .
'
```

## Docker Compose (with devstack)

```yaml
# Add to devstack/docker-compose.yml
services:
  lms-py3:
    image: ltdps/edxapp:py36
    volumes:
      - ../platform:/edx/app/edxapp/edx-platform
    networks:
      - devstack_default
    ports:
      - "18001:8000"
    command: python3 manage.py lms runserver 0.0.0.0:8000 --settings=devstack_docker
```

## Notes

- celery 3.1 + kombu 3.0 kept unchanged (async = soft keyword on 3.6)
- mysqlclient 1.4.6 (Juniper bridge version, dual Py2/3 compat)
- pymongo 3.9.0 + mongoengine 0.10.0 (Juniper-verified combo)
- Django 1.11.29 (officially supports Py3.5-3.7)
- Platform source is volume-mounted, not baked into image
- Network must be `devstack_default` to reach MySQL/Mongo
- Shared DB safety: use separate py3 schema for migrations

## P0-B/P0-C isolated test runners

The R1 runtime image remains unchanged and does not receive pytest. The two
runner images are disposable derivatives with separate test-tool freezes:

The Py2 runner also installs the fixed `edx-search` source that normal
Devstack supplies through a separate mount; the accepted `m5-fixed` image has
only the empty mount point.

```bash
cd /Users/noahwang/workspace/hawthorn/devstack-py36-integration-r1/docker/py36

DOCKER_BUILDKIT=0 docker build --no-cache \
  -f Dockerfile.py36-test-runner \
  -t ltdps/edxapp:py36-r1-p0c-py36-runner-nose2-20260731 .

DOCKER_BUILDKIT=0 docker build --no-cache --platform linux/amd64 \
  -f Dockerfile.py27-test-runner \
  -t ltdps/edxapp:py36-r1-p0c-py27-runner-wiki3-20260731 .
```

Run identity or collection through the guarded wrapper. It refuses to mount
the protected Platform checkout and mounts only `platform-py3-integration` as
read-only. The test settings use disposable SQLite/locmem/eager-Celery state
and runner-specific Mongo and queue names.

```bash
./run-test-runner.sh py36 identity
./run-test-runner.sh py36 lms
./run-test-runner.sh py36 xmodule
./run-test-runner.sh py27 identity
./run-test-runner.sh py27 lms
./run-test-runner.sh py27 xmodule
./run-test-runner.sh py36 focused-collect
./run-test-runner.sh py27 focused-collect
./run-test-runner.sh py36 focused
./run-test-runner.sh py27 focused
./run-test-runner.sh py36 p1b-batch2-collect
./run-test-runner.sh py27 p1b-batch2-collect
./run-test-runner.sh py36 p1b-batch2
./run-test-runner.sh py27 p1b-batch2
```

The selected dual-runtime collection targets are
`lms/djangoapps/static_template_view/tests/test_views.py` and
`common/lib/xmodule/xmodule/tests/test_raw_module.py`.

The `focused` target runs the eight post-`43d2b8f` regression files selected by
the R1 next-gates plan with explicit pytest-django loading and isolated SQLite,
Mongo, cache, and Celery settings. The runtime image and its freeze are never
modified by either runner build.

The `p1b-batch2-collect` and `p1b-batch2` targets run the isolated enrollment,
recent-enrollment, and recent-enrollment-filter checkpoint. The wrapper
defaults to the final Batch 2 r2 runner images and dedicated Batch 2
namespaces. Override the runner image and namespace environment variables only
when reproducing a different recorded checkpoint.

The Py3 runner's test-only freeze also includes the Platform testing pins
`factory_boy==2.8.1` and `Faker==0.8.16`; these are not admitted to the R1
runtime image.

P0-C was accepted on 2026-07-31 at Devstack commit
`c097be389b4b32ffe068cd9b05afb69599a6add7`: both runtimes executed the same
118 focused nodes successfully (Py3.6: 118 passed, 82 warnings; Py2.7: 118
passed, 9 warnings). The final local runner images are
`ltdps/edxapp:py36-r1-p0c-py36-runner-nose2-20260731` and
`ltdps/edxapp:py36-r1-p0c-py27-runner-wiki3-20260731`. The accepted runtime
image at that checkpoint was
`ltdps/edxapp:py36-r1-locked@sha256:7c5a37e...`; the Py2
runner's two `pip check` conflicts are inherited from `m5-fixed` and are
recorded in the Platform evidence.

P1-A was accepted on 2026-08-02 from Devstack commit
`dfd571d61f7b1f885166a5c92d8d64c112c15e58`, tree
`c069178bd4016e69e0ba63c837a5027fddd3452d`. The no-cache build pins
xblock-poll at merged SHA `e8eed047d79ce424b0f9c980b43d48fdeb92517c`
and used the parameterized Tsinghua HTTPS Debian mirrors. The accepted local
runtime is `ltdps/edxapp:py36-r1-locked` at
`sha256:08d4d0452a3fde20f557ddca5c77aac7e1eb78c7fb4dee6e9b855b96d872152f`.
The 226-line freeze and complete service/Celery admission evidence are in the
Platform integration docs. No image registry push was issued.

P1-B Batch 2 review remediation was accepted on 2026-08-02 with Platform
source `430dc13caf787b899ddc16ae900ca569e121af62` and Devstack runner/wrapper
input `0c83125d75ee45f532178bc44134dd3f1b259035`. Both runtimes passed the same
38-node Batch 2 selection, repeated execution, and the 118-node P0-C
regression. The accepted runtime and runner images were unchanged. The next
gate is the separately isolated LMS dashboard/browser workflow; broad
subsystem burn-down remains later P1-B work.
