#!/bin/sh
# Export the private xblock-ilt source at one exact commit. The export is the
# `xblock_ilt` build context of the Python 3.6 image and the /edx/src/xblock-ilt
# mount of the Python 2.7 E6 control, so both runtimes run the same ILT code.
# usage: r2-export-xblock-ilt.sh [out-dir]
# Prints the content digest that the Dockerfile verifies (XBLOCK_ILT_TREE_SHA256).
set -eu

COMMIT=52b0f1cb1f49858a6bfd9a4663c09eec73c5918c
REPO=git@github.com:Learningtribes/xblock-ilt.git
OUT=${1:-/Users/noahwang/workspace/hawthorn/.py36-r2-sources/xblock-ilt-${COMMIT}}

if [ -e "${OUT}" ]; then echo "refusing to overwrite ${OUT}" >&2; exit 2; fi
tmp=$(mktemp -d)
trap 'rm -rf "${tmp}"' EXIT

GIT_SSH_COMMAND='ssh -o BatchMode=yes' git clone --quiet --no-checkout "${REPO}" "${tmp}/repo"
git -C "${tmp}/repo" cat-file -e "${COMMIT}^{commit}"
git -C "${tmp}/repo" merge-base --is-ancestor "${COMMIT}" origin/hawthorn
mkdir -p "${OUT}"
git -C "${tmp}/repo" archive "${COMMIT}" | tar -x -C "${OUT}"
digest=$(cd "${OUT}" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1)
{
    echo "repo=${REPO}"
    echo "commit=${COMMIT}"
    echo "tree=$(git -C "${tmp}/repo" rev-parse "${COMMIT}^{tree}")"
    echo "hawthorn_tip=$(git -C "${tmp}/repo" rev-parse origin/hawthorn)"
    echo "files=$(find "${OUT}" -type f | wc -l | tr -d ' ')"
    echo "content_sha256=${digest}"
} > "${OUT}.identity"
chmod -R a-w "${OUT}"
cat "${OUT}.identity"
