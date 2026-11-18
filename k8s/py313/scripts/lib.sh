# shellcheck shell=bash
# Shared helpers of the local OrbStack scripts. Sourced, not executed.
set -Eeuo pipefail
umask 077

SCRIPTS_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
K8S_DIR=$(cd "$SCRIPTS_DIR/.." && pwd)
OVERLAY=$K8S_DIR/overlays/orbstack-local
LOCAL_DIR=${LOCAL_DIR:-$K8S_DIR/.local}
SECRETS_DIR=$LOCAL_DIR/secrets

# Fixed on purpose: no variable can point these scripts at another namespace.
readonly NS=py313-prod-local
readonly NS_LABEL=app.kubernetes.io/part-of=openedx
CTX=${ALLOW_CONTEXT:-orbstack}
ES_ROLE=py313_search
ES_USER=py313_search
CONFIG_MOUNT=/edx/app/edxapp/py313-config

step() { printf '\n== %s\n' "$*"; }
note() { printf '   %s\n' "$*"; }
die() { printf 'FAIL   %s\n' "$*" >&2; exit 1; }

# Refuses to run against any cluster but the OrbStack one (ALLOW_CONTEXT=<name> is the documented, explicit override).
# Every kubectl call below passes --context itself, so a later `kubectl config use-context` cannot redirect a running script.
require_context() {
  command -v kubectl >/dev/null || die 'kubectl is not installed'
  local current
  current=$(kubectl config current-context 2>/dev/null) || die 'no current kubectl context'
  [ "$current" = "$CTX" ] || die "current kubectl context is '$current', expected '$CTX' (set ALLOW_CONTEXT=<name> to override on purpose)"
}

k() { kubectl --context "$CTX" -n "$NS" "$@"; }
kc() { kubectl --context "$CTX" "$@"; }

# Destructive steps additionally prove that the namespace is the one these scripts created.
require_owned_namespace() {
  [ "$NS" = py313-prod-local ] || die "namespace guard: '$NS' is not py313-prod-local"
  local labels
  labels=$(kc get namespace "$NS" -o jsonpath='{.metadata.labels.app\.kubernetes\.io/part-of}' 2>/dev/null) \
    || die "namespace $NS does not exist"
  [ "$labels" = openedx ] || die "namespace $NS lacks the label $NS_LABEL: not created by these scripts"
}

image_tag() { # the overlay is the single source of truth for the image
  sed -n 's/^[[:space:]]*newTag:[[:space:]]*//p' "$OVERLAY/kustomization.yaml" | head -n 1
}
app_image() { printf 'edxapp:%s\n' "$(image_tag)"; }

require_image() {
  docker image inspect "$(app_image)" >/dev/null 2>&1 || die "image $(app_image) is not in the local Docker daemon (build it: docker/py313/app/README.md)"
}

ensure_local_dir() {
  install -d -m 700 "$LOCAL_DIR" "$SECRETS_DIR"
  chmod 700 "$LOCAL_DIR" "$SECRETS_DIR"
}

secret_file() { printf '%s/%s\n' "$SECRETS_DIR" "$1"; }
secret_value() { cat "$(secret_file "$1")"; }
require_secret_files() {
  local name
  for name in "$@"; do [ -s "$(secret_file "$name")" ] || die "missing $(secret_file "$name"): run scripts/gen-local-secrets"; done
}

# Server-side apply keeps the Secret data out of the kubectl.kubernetes.io/last-applied-configuration annotation.
apply_secret_stream() { k apply --server-side --force-conflicts --field-manager=py313-local -f -; }

wait_rollout() { # wait_rollout KIND/NAME [timeout]
  k rollout status "$1" --timeout="${2:-600s}" >/dev/null && note "ready: $1" || {
    k describe "$1" | tail -n 25 >&2 || true
    die "$1 did not become ready"
  }
}
