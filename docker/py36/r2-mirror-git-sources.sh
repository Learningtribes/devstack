#!/bin/sh
# Mirror every pinned GitHub commit of py36-git-requirements.txt into local
# bare repositories for the `git_mirror` build context of the Python 3.6 image.
# usage: r2-mirror-git-sources.sh [out-dir]
#
# Debian's GnuTLS git intermittently loses the TLS handshake through the build
# proxy (about 1 in 20 connections; a build makes ~40), while the host git does
# not. The image build rewrites https://github.com/ to this mirror with
# url.insteadOf, so requirement URLs, commits and pip metadata stay unchanged.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
LOCK=${SCRIPT_DIR}/py36-git-requirements.txt
OUT=${1:-/Users/noahwang/workspace/hawthorn/.py36-r2-sources/git-mirror-$(shasum -a 256 "${LOCK}" | cut -c1-12)}
ATTEMPTS=3

if [ -e "${OUT}" ]; then echo "refusing to overwrite ${OUT}" >&2; exit 2; fi
mkdir -p "${OUT}"
: > "${OUT}.identity.tmp"

sed -n 's|^git+https://github.com/\([^@]*\)@\([0-9a-f]\{40\}\).*|\1 \2|p' "${LOCK}" | while read -r path sha; do
    repo=${OUT}/${path}
    git init --quiet --bare "${repo}"
    n=1
    until git -C "${repo}" fetch --quiet --no-tags "https://github.com/${path}" "${sha}:refs/heads/pinned"; do
        if [ "${n}" -ge "${ATTEMPTS}" ]; then echo "fetch failed: ${path}@${sha}" >&2; exit 1; fi
        n=$((n + 1))
    done
    test "$(git -C "${repo}" rev-parse refs/heads/pinned)" = "${sha}"
    git -C "${repo}" symbolic-ref HEAD refs/heads/pinned
    echo "${path} ${sha} tree=$(git -C "${repo}" rev-parse "${sha}^{tree}") attempts=${n}" >> "${OUT}.identity.tmp"
done

expected=$(grep -c '^git+https://github.com/' "${LOCK}")
test "$(wc -l < "${OUT}.identity.tmp" | tr -d ' ')" = "${expected}"
{
    echo "lock=py36-git-requirements.txt sha256=$(shasum -a 256 "${LOCK}" | cut -d' ' -f1)"
    echo "repos=${expected}"
    cat "${OUT}.identity.tmp"
} > "${OUT}.identity"
rm -f "${OUT}.identity.tmp"
chmod -R a-w "${OUT}"
cat "${OUT}.identity"
