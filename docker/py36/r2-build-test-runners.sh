#!/bin/bash
# Build the R2-preview E5 test runners and verify their base identity:
# r2-build-test-runners.sh <log-dir> [all|py36|py27]
set -euo pipefail
LOG=$1
WHICH=${2:-all}
cd "$(dirname -- "$0")"
mkdir -p "${LOG}"

PY36_RUNTIME_ID=sha256:8c2e7df2e03d5155be22b6bb70d885a9f88987ff1f74f7ac6a2d1b31165d0355
PY27_RUNTIME_ID=sha256:50b4a73f4814dcc1d41b0da983346990ceb2e31f8c08b1db6093e751c2743b19
PY36_RUNNER=ltdps/edxapp:py36-r2-py36-runner-20261009
PY27_RUNNER=ltdps/edxapp:py36-r2-py27-runner-20261009
PROXY=http://host.docker.internal:7890

test "$(docker image inspect --format '{{.Id}}' ltdps/edxapp:py36-r2-20261009)" = "${PY36_RUNTIME_ID}"

if [ "${WHICH}" != py27 ]; then
    docker build --progress=plain -f Dockerfile.r2-py36-test-runner -t "${PY36_RUNNER}" . \
        > "${LOG}/build-py36-runner.log" 2>&1
fi
if [ "${WHICH}" != py36 ]; then
    docker build --progress=plain --platform linux/amd64 \
        --build-arg "http_proxy=${PROXY}" --build-arg "https_proxy=${PROXY}" \
        -f Dockerfile.r2-py27-test-runner -t "${PY27_RUNNER}" . \
        > "${LOG}/build-py27-runner.log" 2>&1
fi

layers() { docker image inspect --format '{{range .RootFS.Layers}}{{println .}}{{end}}' "$1" | sed '/^$/d'; }
check_prefix() {
    base_layers=$(layers "$1"); runner_layers=$(layers "$2")
    n=$(printf '%s\n' "${base_layers}" | wc -l | tr -d ' ')
    if [ "$(printf '%s\n' "${runner_layers}" | head -n "${n}")" != "${base_layers}" ]; then
        echo "BASE_MISMATCH runner=$2 base=$1" >&2
        exit 1
    fi
    echo "base_layers_prefix_ok runner=$2 base=$1 base_layers=${n} runner_layers=$(printf '%s\n' "${runner_layers}" | wc -l | tr -d ' ')"
}

{
    check_prefix "${PY36_RUNTIME_ID}" "${PY36_RUNNER}"
    check_prefix "${PY27_RUNTIME_ID}" "${PY27_RUNNER}"
    for image in "${PY36_RUNNER}" "${PY27_RUNNER}"; do
        docker image inspect --format "runner=${image} id={{.Id}} arch={{.Architecture}} created={{.Created}}" "${image}"
    done
    grep -h 'test tools OK' "${LOG}"/build-*-runner.log | sed 's/^#[0-9]* [0-9.]* //'
} | tee "${LOG}/runner-identity.txt"
