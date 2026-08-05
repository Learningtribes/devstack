#!/usr/bin/env bash
set -euo pipefail

C2_ID="py36-c2-amd64-20260805-r1"
PROTECTED_PLATFORM="/Users/noahwang/workspace/hawthorn/platform"
PROTECTED_DEVSTACK="/Users/noahwang/workspace/hawthorn/devstack"
PLATFORM_WORKTREE="/private/tmp/${C2_ID}-platform"
DEVSTACK_WORKTREE="/private/tmp/${C2_ID}-devstack"
PLATFORM_COMMIT="b104c1e8031f36ae798e04541f19fb83afbe522f"
PLATFORM_TREE="3e2b85a0a5ef9ca65c4de74e6f49fc7dd0dc9eb7"
DEVSTACK_PARENT="d750e3b1bbb6fe8e75893354921e756399b44fa5"
EVIDENCE_ROOT="${C2_EVIDENCE_ROOT:-/Users/noahwang/workspace/hawthorn/platform-py3-integration/docs/migration_discussion/evidence/python36-c2-amd64-reproducibility-20260805}"
UV_ROOT="/private/tmp"

BASE_ARM64_TAG="${C2_ID}-base-arm64"
BASE_AMD64_TAG="${C2_ID}-base-amd64"
RUNTIME_ARM64_TAG="${C2_ID}-runtime-arm64"
RUNTIME_AMD64_TAG="${C2_ID}-runtime-amd64"
ASSETS_AMD64_TAG="${C2_ID}-assets-amd64"

die() {
    printf '%s\n' "C2 BLOCKER: $*" >&2
    exit 2
}

require_exact_evidence_root() {
    test "${EVIDENCE_ROOT}" = "/Users/noahwang/workspace/hawthorn/platform-py3-integration/docs/migration_discussion/evidence/python36-c2-amd64-reproducibility-20260805" || die "unexpected evidence root: ${EVIDENCE_ROOT}"
    test -d "${EVIDENCE_ROOT}" || die "evidence root is missing: ${EVIDENCE_ROOT}"
}

assert_not_protected() {
    test "$1" != "${PROTECTED_PLATFORM}" || die "refusing protected Platform root"
    test "$1" != "${PROTECTED_DEVSTACK}" || die "refusing protected Devstack root"
}

assert_platform_source() {
    assert_not_protected "${PLATFORM_WORKTREE}"
    test "$(git -C "${PLATFORM_WORKTREE}" rev-parse HEAD)" = "${PLATFORM_COMMIT}" || die "Platform commit drift"
    test "$(git -C "${PLATFORM_WORKTREE}" rev-parse HEAD^{tree})" = "${PLATFORM_TREE}" || die "Platform tree drift"
    test -z "$(git -C "${PLATFORM_WORKTREE}" status --porcelain=v1)" || die "Platform source worktree is dirty"
}

assert_devstack_source() {
    assert_not_protected "${DEVSTACK_WORKTREE}"
    test -z "$(git -C "${DEVSTACK_WORKTREE}" status --porcelain=v1)" || die "Devstack source worktree is dirty"
    test "$(git -C "${DEVSTACK_WORKTREE}" rev-parse HEAD^)" = "${DEVSTACK_PARENT}" || die "Devstack build commit parent drift"
    actual_paths=$(git -C "${DEVSTACK_WORKTREE}" diff-tree --no-commit-id --name-only -r HEAD^ HEAD | LC_ALL=C sort)
    expected_paths=$(printf '%s\n' \
        docker/py36/Dockerfile.c2-base \
        docker/py36/Dockerfile.c2-runtime \
        docker/py36/Dockerfile.c2-assets \
        docker/py36/c2-asset-builder-requirements.txt \
        docker/py36/c2_asset_lms_settings.py \
        docker/py36/c2_asset_cms_settings.py \
        docker/py36/run-c2-amd64-reproducibility.sh | LC_ALL=C sort)
    test "${actual_paths}" = "${expected_paths}" || die "Devstack commit path drift: ${actual_paths}"
}

assert_tag_absent() {
    if docker image inspect "$1" >/dev/null 2>&1; then
        die "refusing existing image tag: $1"
    fi
}

assert_platform_image() {
    expected_platform="$1"
    image_tag="$2"
    actual_platform=$(docker image inspect "${image_tag}" --format '{{.Os}}/{{.Architecture}}')
    test "${actual_platform}" = "${expected_platform}" || die "image platform mismatch: ${image_tag}: ${actual_platform}"
}

record_image() {
    image_tag="$1"
    mkdir -p "${EVIDENCE_ROOT}/images"
    docker image inspect "${image_tag}" > "${EVIDENCE_ROOT}/images/${image_tag}.inspect.json"
    docker history --no-trunc "${image_tag}" > "${EVIDENCE_ROOT}/images/${image_tag}.history.txt"
}

run_logged() {
    phase="$1"
    name="$2"
    cwd="$3"
    command_text="$4"
    mkdir -p "${EVIDENCE_ROOT}/logs/${phase}"
    log_file="${EVIDENCE_ROOT}/logs/${phase}/${name}.log"
    start_epoch=$(date +%s)
    {
        printf '%s\n' "start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        printf '%s\n' "working_directory=${cwd}"
        printf '%s\n' "command=${command_text}"
        printf '%s\n' "platform_commit=${PLATFORM_COMMIT} platform_tree=${PLATFORM_TREE}"
        printf '%s\n' "devstack_commit=$(git -C "${DEVSTACK_WORKTREE}" rev-parse HEAD) devstack_tree=$(git -C "${DEVSTACK_WORKTREE}" rev-parse HEAD^{tree})"
    } > "${log_file}"
    set +e
    (cd "${cwd}" && bash -o pipefail -c "${command_text}") >> "${log_file}" 2>&1
    status=$?
    set -e
    {
        printf '%s\n' "exit=${status}"
        printf '%s\n' "wall_seconds=$(( $(date +%s) - start_epoch ))"
        printf '%s\n' "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } >> "${log_file}"
    cat "${log_file}"
    return "${status}"
}

build_base() {
    arch="$1"
    case "${arch}" in
        arm64)
            target_platform="linux/arm64"
            base_manifest="sha256:ac11ce85a603a835533b2ec608246fef2fea4a4b4790df97a20d9cce7032faf6"
            uv_context="${UV_ROOT}/${C2_ID}-uv-aarch64-context"
            uv_url="https://github.com/astral-sh/uv/releases/download/0.1.44/uv-aarch64-unknown-linux-gnu.tar.gz"
            uv_sha="afb7039f033546d55730dae38a106dd56b358117a565a42bf3ebda9c48db53c6"
            uv_dir="uv-aarch64-unknown-linux-gnu"
            image_tag="${BASE_ARM64_TAG}"
            ;;
        amd64)
            target_platform="linux/amd64"
            base_manifest="sha256:28028f6c3ce569a6405909ca76e85469fbb85c9ee93acd2fe5fe13f5e5e2c412"
            uv_context="${UV_ROOT}/${C2_ID}-uv-x86_64-context"
            uv_url="https://github.com/astral-sh/uv/releases/download/0.1.44/uv-x86_64-unknown-linux-gnu.tar.gz"
            uv_sha="68e8fda65c987cc104bdf7ae1eb332477733d44a27823032826f9370928568b2"
            uv_dir="uv-x86_64-unknown-linux-gnu"
            image_tag="${BASE_AMD64_TAG}"
            ;;
        *) die "unsupported base architecture: ${arch}" ;;
    esac
    require_exact_evidence_root
    assert_platform_source
    assert_devstack_source
    test -d "${uv_context}" || die "missing uv context: ${uv_context}"
    test "$(sha256sum "${uv_context}/uv.tar.gz" | awk '{print $1}')" = "${uv_sha}" || die "uv context hash drift"
    assert_tag_absent "${image_tag}"
    devstack_commit=$(git -C "${DEVSTACK_WORKTREE}" rev-parse HEAD)
    devstack_tree=$(git -C "${DEVSTACK_WORKTREE}" rev-parse HEAD^{tree})
    build_command="docker buildx build --builder orbstack --progress plain --no-cache --pull=false --platform ${target_platform} --file docker/py36/Dockerfile.c2-base --build-context platform=${PLATFORM_WORKTREE} --build-context uv=${uv_context} --build-arg PYTHON_BASE_IMAGE=python:3.6-slim@${base_manifest} --build-arg BASE_MANIFEST=${base_manifest} --build-arg UV_URL=${uv_url} --build-arg UV_SHA256=${uv_sha} --build-arg UV_ARCHIVE_DIR=${uv_dir} --build-arg DEBIAN_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian --build-arg DEBIAN_SECURITY_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian-security --build-arg PLATFORM_COMMIT=${PLATFORM_COMMIT} --build-arg PLATFORM_TREE=${PLATFORM_TREE} --build-arg DEVSTACK_BUILD_COMMIT=${devstack_commit} --build-arg DEVSTACK_BUILD_TREE=${devstack_tree} --tag ${image_tag} --load ."
    run_logged build "base-${arch}" "${DEVSTACK_WORKTREE}" "${build_command}"
    assert_platform_image "linux/${arch}" "${image_tag}"
    record_image "${image_tag}"
}

build_runtime() {
    arch="$1"
    case "${arch}" in
        arm64) target_platform="linux/arm64"; base_tag="${BASE_ARM64_TAG}"; image_tag="${RUNTIME_ARM64_TAG}" ;;
        amd64) target_platform="linux/amd64"; base_tag="${BASE_AMD64_TAG}"; image_tag="${RUNTIME_AMD64_TAG}" ;;
        *) die "unsupported runtime architecture: ${arch}" ;;
    esac
    require_exact_evidence_root
    assert_platform_source
    assert_devstack_source
    base_id_before=$(docker image inspect "${base_tag}" --format '{{.Id}}')
    assert_tag_absent "${image_tag}"
    devstack_commit=$(git -C "${DEVSTACK_WORKTREE}" rev-parse HEAD)
    devstack_tree=$(git -C "${DEVSTACK_WORKTREE}" rev-parse HEAD^{tree})
    build_command="docker buildx build --builder orbstack --progress plain --no-cache --pull=false --platform ${target_platform} --file docker/py36/Dockerfile.c2-runtime --build-arg BASE_IMAGE=${base_tag} --build-arg PLATFORM_COMMIT=${PLATFORM_COMMIT} --build-arg PLATFORM_TREE=${PLATFORM_TREE} --build-arg DEVSTACK_BUILD_COMMIT=${devstack_commit} --build-arg DEVSTACK_BUILD_TREE=${devstack_tree} --build-arg ORA2_COMMIT=d3f24a9c539528e960c8dcc9aef200cea0c49baf --build-arg SUBMISSIONS_PATCH_SHA256=00b289b42748b93e314fbb8cf90117778ceadac4789f7ec234fc9ef554b31acf --tag ${image_tag} --load ."
    run_logged build "runtime-${arch}" "${DEVSTACK_WORKTREE}" "${build_command}"
    base_id_after=$(docker image inspect "${base_tag}" --format '{{.Id}}')
    test "${base_id_before}" = "${base_id_after}" || die "base tag changed during derivative build: ${base_tag}"
    assert_platform_image "linux/${arch}" "${image_tag}"
    record_image "${image_tag}"
}

case "${1:-}" in
    build-base)
        test "$#" -eq 2 || die "usage: $0 build-base arm64|amd64"
        build_base "$2"
        ;;
    build-runtime)
        test "$#" -eq 2 || die "usage: $0 build-runtime arm64|amd64"
        build_runtime "$2"
        ;;
    guard)
        require_exact_evidence_root
        assert_platform_source
        assert_devstack_source
        ;;
    *)
        die "usage: $0 {guard|build-base|build-runtime} arm64|amd64"
        ;;
esac
