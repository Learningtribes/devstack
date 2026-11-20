#!/usr/bin/env bash
# Build the py3-master application image from two committed trees. No registry or git credentials reach the build.
#
# Usage: PLATFORM_REPO=<clone> THEME_REPO=<clone> build.sh <image-tag> [native|amd64|arm64]
#        PLATFORM_REPO=<clone> THEME_REPO=<clone> build.sh --check
#
# Inputs:   commits come from inputs.env; PLATFORM_COMMIT / THEME_COMMIT in the environment override them.
# Policy:   the tag needs an explicit version part and must not be `latest`; a tag that already exists locally is
#           refused unless FORCE=1. The architecture defaults to the host's; amd64 only on explicit request.
# Output:   $BUILD_DIR/image.lock.json (default: build/ next to this script, git-ignored).
# Extras:   BUILDX_FLAGS (default --load), e.g. BUILDX_FLAGS="--push --progress=plain" or "--load --build-arg APP_UID=1001".
# The positional form `build.sh PLATFORM_REPO PLATFORM_COMMIT THEME_REPO THEME_COMMIT TAG [platform]` was removed:
# set PLATFORM_REPO/THEME_REPO and, only when deviating from inputs.env, PLATFORM_COMMIT/THEME_COMMIT.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
die() { echo "build.sh: $*" >&2; exit 2; }
usage() { sed -n '2,12p' "$0" >&2; exit 2; }

mode=build tag='' arch=native
case "${1:-}" in
  --check) mode=check; [ $# -eq 1 ] || usage ;;
  -h|--help|'') usage ;;
  *) [ $# -le 2 ] || die "the positional PLATFORM_REPO PLATFORM_COMMIT THEME_REPO THEME_COMMIT form was removed; see usage"
     tag=$1 arch=${2:-native} ;;
esac

# Environment wins over the pinned file; the file is parsed, never sourced.
while IFS='=' read -r key value; do
  case "$key" in
    PLATFORM_COMMIT|THEME_COMMIT) [ -n "${!key:-}" ] || printf -v "$key" '%s' "$value" ;;
  esac
done < "$here/inputs.env"
: "${PLATFORM_COMMIT:?not set and missing from inputs.env}" "${THEME_COMMIT:?not set and missing from inputs.env}"
: "${PLATFORM_REPO:?set PLATFORM_REPO to a local clone of https://github.com/Learningtribes/platform}"
: "${THEME_REPO:?set THEME_REPO to a local clone of https://github.com/Learningtribes/triboo-theme}"

if [ "$mode" = build ]; then
  [[ "${tag##*/}" == *:* ]] || die "tag '$tag' has no explicit version part (use name:version)"
  [ "${tag##*:}" != latest ] || die "tag 'latest' is refused; use an immutable version tag"
  [[ "$tag" =~ ^[a-z0-9]+([._/:-]+[A-Za-z0-9]+)*$ && "${tag##*:}" =~ ^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$ ]] \
    || die "tag '$tag' is not a valid image reference"
  if [ "${FORCE:-0}" != 1 ] && docker image inspect "$tag" >/dev/null 2>&1; then
    die "image '$tag' already exists locally; choose a new tag or set FORCE=1"
  fi
fi

case "$arch" in
  native) case "$(uname -m)" in
            arm64|aarch64) target=linux/arm64 ;;
            x86_64|amd64) target=linux/amd64 ;;
            *) die "unsupported host architecture $(uname -m)" ;;
          esac ;;
  amd64|linux/amd64) target=linux/amd64 ;;
  arm64|linux/arm64) target=linux/arm64 ;;
  *) die "unknown platform '$arch' (native, amd64 or arm64)" ;;
esac

resolve() { # resolve REPO COMMIT -> full sha
  [[ "$2" =~ ^[0-9a-f]{7,40}$ ]] || die "commit must be 7+ hex characters, got: $2"
  git -C "$1" rev-parse --verify "$2^{commit}" 2>/dev/null || die "commit $2 not found in $1"
}
platform_sha=$(resolve "$PLATFORM_REPO" "$PLATFORM_COMMIT")
theme_sha=$(resolve "$THEME_REPO" "$THEME_COMMIT")

work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
mkdir "$work/platform" "$work/theme"
git -C "$PLATFORM_REPO" archive "$platform_sha" | tar -x -C "$work/platform"
git -C "$THEME_REPO" archive "$theme_sha" | tar -x -C "$work/theme"

args=(--platform "$target"
  --build-context "platform=$work/platform" --build-context "theme=$work/theme"
  --build-arg "PLATFORM_COMMIT=$platform_sha" --build-arg "THEME_COMMIT=$theme_sha"
  -f "$here/app.Dockerfile")

if [ "$mode" = check ]; then
  docker buildx build --check "${args[@]}" "$here"
  exit
fi

meta=$work/metadata.json
# shellcheck disable=SC2086
docker buildx build "${args[@]}" --metadata-file "$meta" -t "$tag" ${BUILDX_FLAGS:---load} "$here"

meta_value() { sed -n "s/.*\"$1\": *\"\([^\"]*\)\".*/\1/p" "$meta" | head -n 1; }
index_digest=''
case "${BUILDX_FLAGS:-}" in *--push*|*push=true*) index_digest=$(meta_value containerimage.digest) ;; esac
# --push without --load leaves no local image: fall back to the build metadata.
if image_id=$(docker image inspect --format '{{.Id}}' "$tag" 2>/dev/null); then
  architecture=$(docker image inspect --format '{{.Architecture}}' "$tag")
else
  image_id=$(meta_value containerimage.config.digest) architecture=${target#linux/}
fi

build_dir=${BUILD_DIR:-$here/build}
mkdir -p "$build_dir"
{
  printf '{\n'
  printf '  "tag": "%s",\n' "$tag"
  printf '  "image_id": "%s",\n' "$image_id"
  printf '  "architecture": "%s",\n' "$architecture"
  printf '  "platform_sha": "%s",\n' "$platform_sha"
  printf '  "theme_sha": "%s",\n' "$theme_sha"
  printf '  "build_date": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [ -n "$index_digest" ]; then printf '  "index_digest": "%s"\n' "$index_digest"; else printf '  "index_digest": null\n'; fi
  printf '}\n'
} > "$build_dir/image.lock.json"
echo "build.sh: wrote $build_dir/image.lock.json"
