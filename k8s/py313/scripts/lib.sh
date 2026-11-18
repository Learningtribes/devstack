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

# Traefik mode (INGRESS=traefik). Namespaces and the label that marks everything this feature created are fixed like NS above.
readonly TNS=traefik
readonly BASE_DOMAIN=local-prod.7mud.com
readonly FEATURE_LABEL_KEY=py313.learningtribes.com/feature
readonly FEATURE_LABEL=py313.learningtribes.com/feature=traefik-local
readonly MODE_ANNOTATION=py313.learningtribes.com/ingress-mode
TRAEFIK_DIR=$K8S_DIR/traefik
TRAEFIK_OVERLAY=$K8S_DIR/overlays/orbstack-local-traefik
TLS_DIR=$LOCAL_DIR/tls

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
kt() { kubectl --context "$CTX" -n "$TNS" "$@"; }
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

# INGRESS is unset (kubectl port-forward, http://localhost:18000 / :18010) or `traefik` (https://{lms,studio}.local-prod.7mud.com).
ingress_mode() {
  case "${INGRESS:-}" in
    '') echo port-forward ;;
    traefik) echo traefik ;;
    *) die "INGRESS must be unset or 'traefik', not '${INGRESS}'" ;;
  esac
}

# Non-secret BRINGUP_* values of the selected mode; the Traefik file overrides the base file key by key.
bringup_env_files() {
  printf '%s\n' "$OVERLAY/jobs/bringup.env"
  if [ "$(ingress_mode)" = traefik ]; then printf '%s\n' "$TRAEFIK_OVERLAY/jobs/bringup.env"; fi
}
bringup_value() { # bringup_value KEY
  local file
  while IFS= read -r file; do cat "$file"; done < <(bringup_env_files) | sed -n "s/^$1=//p" | tail -n 1
}
jobs_overlay() { if [ "$(ingress_mode)" = traefik ]; then echo "$TRAEFIK_OVERLAY/jobs"; else echo "$OVERLAY/jobs"; fi; }

# Applies a manifest stream (a Secret or ConfigMap built by kubectl create --dry-run) to a namespace, labelled for traefik-down.
apply_feature_stream() { # apply_feature_stream NAMESPACE
  kubectl label --local -f - -o yaml "$FEATURE_LABEL" \
    | kubectl --context "$CTX" -n "$1" apply --server-side --force-conflicts --field-manager=py313-local -f -
}

# Celery smoke shared by smoke and traefik-smoke; counts failures in the caller's `fails` variable.
celery_check() {
  step 'Celery: one task through the broker to a running worker'
  # A one-off process in the running lms pod (same config, same broker as the web process) calls apply_async on a task of the LMS
  # default queue (edx.lms.core.default, the one worker-lms-default consumes) and waits for the result over the memcached result backend. The task is
  # openedx.core.djangoapps.heartbeat.tasks.sample_task (returns True, no side effects).
  since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  # shellcheck disable=SC2016
  snippet='from openedx.core.djangoapps.heartbeat.tasks import sample_task
r = sample_task.apply_async()
print("TASK_ID", r.id)
print("RESULT", r.get(timeout=60))'
  if output=$(k exec deploy/lms -- edxapp-entrypoint manage lms shell -c "$snippet" 2>&1); then
    echo "$output" | grep -E '^(TASK_ID|RESULT)' | sed 's/^/   producer: /'
    task_id=$(sed -n 's/^TASK_ID \([0-9a-f-]*\)$/\1/p' <<<"$output" | head -n 1)
    if grep -q '^RESULT True$' <<<"$output" && [ -n "$task_id" ]; then
      sleep 2
      line=$(k logs deploy/worker-lms-default --since-time="$since" 2>&1 | grep -F "$task_id" || true)
      echo "$line" | sed 's/^/   worker-lms-default: /'
      if grep -q 'received' <<<"$line" && grep -q 'succeeded' <<<"$line"; then
        printf 'PASS   task %s received and succeeded in worker-lms-default\n' "$task_id"
      else
        printf 'FAIL   worker log of worker-lms-default does not show the task %s\n' "$task_id"; fails=$((fails + 1))
      fi
    else
      printf 'FAIL   task result was not True\n'; fails=$((fails + 1))
    fi
  else
    echo "$output" | tail -n 15 | sed 's/^/   /'
    printf 'FAIL   could not run the producer in the lms pod\n'; fails=$((fails + 1))
  fi
}
