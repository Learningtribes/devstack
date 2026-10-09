#!/bin/sh
# R2-preview E4: Python 3.6 LMS, CMS and worker on an isolated broker and cache.
# usage: run-r2-e4-services.sh {start|status|cleanup|tasks <step>...|shell <lms|cms>}
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
WORKSPACE=/Users/noahwang/workspace/hawthorn
SOURCE_ROOT=${WORKSPACE}/platform-r2-py36-src
CONFIG=${WORKSPACE}/.py36-r2-config
LOG_ROOT=${PY36_R2_E4_LOG_ROOT:-/tmp/py36-r2-e4-20261009}
IMAGE=ltdps/edxapp:py36-r2-20261009
IMAGE_ID=sha256:4560a9c2b264ba25f5cf93bd49ee7e163eb2133e24d537811dbaf45c84d397ce
RABBIT_IMAGE=rabbitmq@sha256:4206c16c09a58d0a604668e91227c32f4a222368e796bfb7bf2e0d0d160ef97a
CACHE_IMAGE=memcached@sha256:ec8ffdf1f1d2b4d7a20ac91359520528fe4a934453f8e058eaf41ac5f7f9e226
NETWORK=devstack_default
LABEL=io.openedx.py36-r2.gate=e4
NAMESPACE=py36-r2
VHOST=py36-r2-20261009
RABBIT=py36-r2-rabbitmq-20261009
CACHE=py36-r2-memcached-20261009
LMS=py36-r2-lms-20261009
CMS=py36-r2-cms-20261009
WORKER=py36-r2-worker-20261009
LMS_PORT=18200
CMS_PORT=18210
BROKER_ENV=${CONFIG}/e4-broker.env
P=/edx/app/edxapp/edx-platform
L=${P}/common/lib
PYTHONPATH_VALUE=/edx/app/edxapp:${P}:${L}/xmodule:${L}/capa:${L}/calc:${L}/safe_lxml:${L}/symmath:${L}/chem:${L}/dogstats
# Without --settings, manage.py keeps DJANGO_SETTINGS_MODULE (the E4 overlay).
# --nostatic: the source worktree has no webpack output, so /static/ must reach
# the URLconf static(STATIC_URL, STATIC_ROOT) route over the collected volume
# instead of the staticfiles finders.

exists() { docker container inspect "$1" >/dev/null 2>&1; }

service_args() {
    svc=$1
    printf '%s\n' \
        --network "${NETWORK}" --label "${LABEL}" --label "io.openedx.py36-r2.service=${svc}" \
        --mount "type=bind,src=${SOURCE_ROOT},dst=${P},readonly" \
        --mount "type=bind,src=${WORKSPACE}/src,dst=/edx/src,readonly" \
        --mount "type=bind,src=${CONFIG}/${svc}.auth.json,dst=/edx/app/edxapp/${svc}.auth.json,readonly" \
        --mount "type=bind,src=${CONFIG}/${svc}.env.json,dst=/edx/app/edxapp/${svc}.env.json,readonly" \
        --mount "type=bind,src=${SCRIPT_DIR}/py36_r2_e4_settings.py,dst=/edx/app/edxapp/py36_r2_e4_settings.py,readonly" \
        --mount "type=bind,src=${SCRIPT_DIR}/py36_r2_e4_worker.py,dst=/edx/app/edxapp/py36_r2_e4_worker.py,readonly" \
        --mount "type=bind,src=${SCRIPT_DIR}/py36_r2_e4_tasks.py,dst=/edx/app/edxapp/py36_r2_e4_tasks.py,readonly" \
        --mount type=tmpfs,dst=/edx/var/edxapp/data \
        --env-file "${BROKER_ENV}" \
        --env "SERVICE_VARIANT=${svc}" --env DJANGO_SETTINGS_MODULE=py36_r2_e4_settings \
        --env "PYTHONPATH=${PYTHONPATH_VALUE}" --env PYTHONDONTWRITEBYTECODE=1 \
        --env "PY36_R2_E4_NAMESPACE=${NAMESPACE}" --env "PY36_R2_E4_CACHE_HOST=${CACHE}" \
        --env "PY36_R2_E4_RABBIT_HOST=${RABBIT}" --env "PY36_R2_E4_RABBIT_VHOST=${VHOST}" \
        --env EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo --env NO_PYTHON_UNINSTALL=1 \
        -w "${P}"
}

wait_for() {
    what=$1; shift
    tries=0
    until "$@" >/dev/null 2>&1; do
        tries=$((tries + 1))
        if [ "${tries}" -ge 120 ]; then echo "timeout waiting for ${what}" >&2; return 1; fi
        sleep 1
    done
}

start() {
    test "$(docker image inspect "${IMAGE}" --format '{{.Id}}')" = "${IMAGE_ID}"
    test -z "$(git -C "${SOURCE_ROOT}" status --porcelain)"
    for c in ${RABBIT} ${CACHE} ${LMS} ${CMS} ${WORKER}; do
        if exists "$c"; then echo "refusing to replace existing container: $c" >&2; exit 2; fi
    done
    for port in ${LMS_PORT} ${CMS_PORT}; do
        if lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then echo "port ${port} in use" >&2; exit 2; fi
    done
    if [ ! -f "${BROKER_ENV}" ]; then
        (umask 077; printf 'PY36_R2_E4_RABBIT_USER=py36r2\nPY36_R2_E4_RABBIT_PASSWORD=%s\n' \
            "$(openssl rand -hex 16)" > "${BROKER_ENV}")
    fi
    mkdir -p "${LOG_ROOT}/lms/lms" "${LOG_ROOT}/lms/cms" "${LOG_ROOT}/cms/lms" "${LOG_ROOT}/cms/cms" \
        "${LOG_ROOT}/worker/lms" "${LOG_ROOT}/worker/cms"
    . "${BROKER_ENV}"

    docker run -d --name "${RABBIT}" --network "${NETWORK}" --label "${LABEL}" \
        --env "RABBITMQ_DEFAULT_USER=${PY36_R2_E4_RABBIT_USER}" \
        --env "RABBITMQ_DEFAULT_PASS=${PY36_R2_E4_RABBIT_PASSWORD}" \
        --env "RABBITMQ_DEFAULT_VHOST=${VHOST}" "${RABBIT_IMAGE}" >/dev/null
    docker run -d --name "${CACHE}" --network "${NETWORK}" --label "${LABEL}" \
        "${CACHE_IMAGE}" memcached -m 64 >/dev/null
    wait_for rabbitmq docker exec "${RABBIT}" rabbitmq-diagnostics -q check_running

    # shellcheck disable=SC2046
    docker run -d --name "${LMS}" --entrypoint /bin/sh --publish "127.0.0.1:${LMS_PORT}:18000" \
        --mount "type=bind,src=${LOG_ROOT}/lms,dst=/edx/var/log" \
        --mount type=volume,src=devstack_edxapp_lms_assets,dst=/edx/var/edxapp/staticfiles,readonly \
        $(service_args lms) "${IMAGE}" -c "exec python manage.py lms runserver 0.0.0.0:18000 --noreload --nostatic" >/dev/null
    # shellcheck disable=SC2046
    docker run -d --name "${CMS}" --entrypoint /bin/sh --publish "127.0.0.1:${CMS_PORT}:18010" \
        --mount "type=bind,src=${LOG_ROOT}/cms,dst=/edx/var/log" \
        --mount type=volume,src=devstack_edxapp_studio_assets,dst=/edx/var/edxapp/staticfiles,readonly \
        $(service_args cms) "${IMAGE}" -c "exec python manage.py cms runserver 0.0.0.0:18010 --noreload --nostatic" >/dev/null
    # shellcheck disable=SC2046
    docker run -d --name "${WORKER}" --entrypoint /bin/sh \
        --mount "type=bind,src=${LOG_ROOT}/worker,dst=/edx/var/log" \
        --env "PY36_R2_E4_WORKER_HOSTNAME=${WORKER}" \
        $(service_args lms) "${IMAGE}" -c "exec python /edx/app/edxapp/py36_r2_e4_worker.py" >/dev/null

    wait_for "LMS heartbeat" curl -fsS -o /dev/null "http://127.0.0.1:${LMS_PORT}/heartbeat"
    wait_for "CMS heartbeat" curl -fsS -o /dev/null "http://127.0.0.1:${CMS_PORT}/heartbeat"
    wait_for "worker ready" sh -c "docker logs ${WORKER} 2>&1 | grep -q PY36_R2_E4_WORKER_READY"
    status
    echo "E4_SERVICES_STARTED lms=http://127.0.0.1:${LMS_PORT} cms=http://127.0.0.1:${CMS_PORT}"
}

status() {
    for c in ${RABBIT} ${CACHE} ${LMS} ${CMS} ${WORKER}; do
        if exists "$c"; then
            docker inspect "$c" --format '{{.Name}} running={{.State.Running}} restarts={{.RestartCount}} image={{.Image}} source_ro={{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/edx-platform"}}{{not .RW}}{{end}}{{end}}'
        else
            echo "/$c absent"
        fi
    done
}

cleanup() {
    for c in ${WORKER} ${LMS} ${CMS} ${CACHE} ${RABBIT}; do
        if exists "$c"; then
            test "$(docker inspect "$c" --format '{{index .Config.Labels "io.openedx.py36-r2.gate"}}')" = e4
            docker rm -f "$c" >/dev/null && echo "removed $c"
        fi
    done
}

case "${1:-}" in
    start) start ;;
    status) status ;;
    cleanup) cleanup ;;
    tasks) shift; docker exec "${WORKER}" python /edx/app/edxapp/py36_r2_e4_tasks.py "$@" ;;
    shell) docker exec -i "$( [ "${2:-}" = cms ] && echo "${CMS}" || echo "${LMS}")" \
               python manage.py "${2:-lms}" shell ;;
    *) echo "usage: $0 {start|status|cleanup|tasks <step>...|shell <lms|cms>}" >&2; exit 2 ;;
esac
