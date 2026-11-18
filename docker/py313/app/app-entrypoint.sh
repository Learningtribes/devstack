#!/usr/bin/env bash
# Entry point of the py313 edxapp image: one process per container, started under tini (PID 1).
#   lms | cms                          gunicorn on 0.0.0.0:$PORT (default 8000 | 8010), logs to stdout
#   worker lms|cms [celery args...]    celery -A <system>.celery:APP worker [args]
#   manage lms|cms [args...]           python manage.py <system> --settings=$EDXAPP_SETTINGS [args]
#   anything else                      executed as given (bash, python, /startup scripts)
# Settings module: <system>.envs.$EDXAPP_SETTINGS (default aws); config JSON in $CONFIG_ROOT/<system>.{env,auth}.json.
# Gunicorn: GUNICORN_WORKERS, GUNICORN_TIMEOUT, GUNICORN_MAX_REQUESTS; any other flag through GUNICORN_CMD_ARGS.
set -euo pipefail

settings=${EDXAPP_SETTINGS:-aws}
case "$settings" in
  ''|*[!a-z0-9_]*) echo "edxapp-entrypoint: invalid EDXAPP_SETTINGS '$settings'" >&2; exit 64 ;;
esac

system_arg() {
  case "${1:-}" in
    lms|cms) ;;
    *) echo "edxapp-entrypoint: expected lms or cms, got '${1:-}'" >&2; exit 64 ;;
  esac
}

require_config() {
  local file
  for file in "$CONFIG_ROOT/$1.env.json" "$CONFIG_ROOT/$1.auth.json"; do
    if [ ! -r "$file" ]; then
      echo "edxapp-entrypoint: $file is missing or not readable by uid $(id -u) (mount the config Secret at CONFIG_ROOT=$CONFIG_ROOT)" >&2
      exit 78
    fi
  done
}

cd "$EDXAPP_HOME/edx-platform"
command=${1:-lms}
[ $# -gt 0 ] && shift

case "$command" in
  lms|cms)
    require_config "$command"
    export SERVICE_VARIANT=$command DJANGO_SETTINGS_MODULE=$command.envs.$settings
    if [ "$command" = lms ]; then port=8000 workers=2 max_requests=1000; else port=8010 workers=1 max_requests=2000; fi
    exec gunicorn "$command.wsgi:application" \
      --bind "0.0.0.0:${PORT:-$port}" \
      --workers "${GUNICORN_WORKERS:-$workers}" \
      --timeout "${GUNICORN_TIMEOUT:-300}" \
      --max-requests "${GUNICORN_MAX_REQUESTS:-$max_requests}" \
      --access-logfile - --error-logfile - \
      --worker-tmp-dir /dev/shm --no-control-socket \
      "$@"
    ;;
  worker)
    system_arg "${1:-}"; system=$1; shift
    require_config "$system"
    export SERVICE_VARIANT=$system DJANGO_SETTINGS_MODULE=$system.envs.$settings
    exec celery -A "$system.celery:APP" worker "$@"
    ;;
  manage)
    system_arg "${1:-}"; system=$1; shift
    require_config "$system"
    exec python manage.py "$system" --settings="$settings" "$@"
    ;;
  *)
    exec "$command" "$@"
    ;;
esac
