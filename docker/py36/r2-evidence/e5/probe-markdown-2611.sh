#!/bin/sh
# Disposable proof for the E5 Markdown finding: run the r2-dcc target on the
# unchanged Python 3.6 runner with Markdown 2.6.11 (the Platform base.txt pin)
# installed into the runner tmpfs and placed first on PYTHONPATH. No image is
# modified. Usage: probe-markdown-2611.sh > out.txt
set -eu
PY36=/Users/noahwang/workspace/hawthorn/devstack-py36-r2-env/docker/py36
SOURCE=/Users/noahwang/workspace/hawthorn/platform-r2-py36-src
test "$(git -C "${SOURCE}" rev-parse HEAD)" = 0ac3bfa6d099916cc58fc258db17221801f49d48
test -z "$(git -C "${SOURCE}" status --porcelain=v1)"

exec docker run --rm \
    --network devstack_default \
    --read-only \
    --tmpfs /runner:rw,exec,size=1g \
    --tmpfs /tmp:rw,exec,size=1g \
    --tmpfs /edx/var/log:rw,exec,size=64m \
    --mount "type=bind,src=${SOURCE},dst=/edx/app/edxapp/edx-platform,readonly" \
    --mount "type=bind,src=${PY36}/test-runner-entrypoint.sh,dst=/opt/runner/test-runner-entrypoint.sh,readonly" \
    --mount "type=bind,src=${PY36}/py36_r1_test_settings.py,dst=/opt/runner/py36_r1_test_settings.py,readonly" \
    --env PY36_R1_TEST_NAMESPACE=py36-r2-e5-mdprobe \
    --env PY36_R1_MONGO_DB_PREFIX=py36-r2-e5-mdprobe \
    --env EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo \
    --env EDXAPP_TEST_MONGO_PORT=27017 \
    --env DISABLE_MIGRATIONS=1 \
    --env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
    --env https_proxy=http://host.docker.internal:7890 \
    --env http_proxy=http://host.docker.internal:7890 \
    --entrypoint /bin/sh \
    ltdps/edxapp:py36-r2-py36-runner-20261009 -c '
        pip install --quiet --no-deps --target /runner/markdown-2.6.11 markdown==2.6.11 &&
        PYTHONPATH=/runner/markdown-2.6.11 python -c "import markdown; print(\"PROBE markdown\", markdown.version, markdown.__file__)" &&
        PYTHONPATH=/runner/markdown-2.6.11 exec /opt/runner/test-runner-entrypoint.sh r2-dcc'
