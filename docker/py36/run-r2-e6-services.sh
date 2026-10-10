#!/bin/sh
# R2-preview E6: per-runtime LMS + Studio on a private MySQL clone and memcached.
# usage: run-r2-e6-services.sh clone
#        run-r2-e6-services.sh {py36|py27} {start|status|cleanup|logs}
#
# `clone` takes one read-only mysqldump of the shared edxapp/edxapp_csmh
# databases; every runtime stack loads the same snapshot into its own MySQL.
# LMS (:18000) and Studio (:18010) share one network namespace so a browser
# joined to it sees the canonical devstack origins (Site rows, absolute Studio
# URLs, cookies) while the host ports stay with the shared Python 2.7 devstack.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
WORKSPACE=/Users/noahwang/workspace/hawthorn
SOURCE_ROOT=${WORKSPACE}/platform-r2-py36-src
EXPECTED_COMMIT=0ac3bfa6d099916cc58fc258db17221801f49d48
CONFIG=${WORKSPACE}/.py36-r2-config
DUMP=${CONFIG}/e6-mysql-snapshot.sql
MYSQL_ENV=${CONFIG}/e6-mysql.env
# The Python 3.6 image installs this exact export; overlaying it on the shared
# src/ checkout keeps the Python 2.7 control's editable ilt-xblock identical.
XBLOCK_ILT_COMMIT=52b0f1cb1f49858a6bfd9a4663c09eec73c5918c
XBLOCK_ILT_SRC=${WORKSPACE}/.py36-r2-sources/xblock-ilt-${XBLOCK_ILT_COMMIT}
# r2-build-e6-assets.sh output; LMS and Studio both mount the runtime's tree.
ASSET_ROOT=${PY36_R2_E6_ASSET_ROOT:-/tmp/py36-r2-e6-assets-20261010-r3}
MYSQL_IMAGE=mysql:5.6
CACHE_IMAGE=memcached@sha256:ec8ffdf1f1d2b4d7a20ac91359520528fe4a934453f8e058eaf41ac5f7f9e226
NETWORK=devstack_default
LABEL=io.openedx.py36-r2.gate=e6
# Gate containers share the Docker VM with edx.devstack.*; without a cgroup
# cap a spike here makes the kernel OOM killer pick the shared Mongo instead.
APP_MEMORY=${PY36_R2_GATE_APP_MEMORY:-2g}
MYSQL_MEMORY=${PY36_R2_GATE_MYSQL_MEMORY:-2g}
P=/edx/app/edxapp/edx-platform
L=${P}/common/lib

clone() {
    umask 077
    if [ ! -f "${MYSQL_ENV}" ]; then
        pw=$(openssl rand -hex 16)
        printf 'MYSQL_ROOT_PASSWORD=%s\nPY36_R2_E6_MYSQL_ROOT_PASSWORD=%s\n' "${pw}" "${pw}" > "${MYSQL_ENV}"
    fi
    docker exec edx.devstack.mysql mysqldump -uroot --single-transaction --routines --triggers \
        --databases edxapp edxapp_csmh > "${DUMP}.tmp"
    mv "${DUMP}.tmp" "${DUMP}"
    echo "E6_CLONE_DONE at=$(date -u +%Y-%m-%dT%H:%M:%SZ) bytes=$(wc -c < "${DUMP}" | tr -d ' ') sha256=$(shasum -a 256 "${DUMP}" | cut -d' ' -f1)"
}

if [ "${1:-}" = clone ]; then clone; exit 0; fi

RUNTIME=${1:-}
case "${RUNTIME}" in
    py36)
        IMAGE=ltdps/edxapp:py36-r2-20261009
        IMAGE_ID=sha256:9b43579930c4cd53e77e1fc5cfe1100f8852c605f1dfa8e9ab924fa2503f2211
        PLATFORM=linux/arm64
        PYTHON=python
        PORT_BASE=183
        METADATA=
        ;;
    py27)
        IMAGE=ltdps/edxapp:py36-r2-py27-runner-20261009
        IMAGE_ID=sha256:e5ecccf98eb9b9f9d7cb04d7f04a08d62cf29ce19a7e8f3c2230e5cf67396b89
        PLATFORM=linux/amd64
        PYTHON=/edx/app/edxapp/venvs/edxapp/bin/python
        PORT_BASE=184
        METADATA="${PYTHON} /opt/runner/py27_source_metadata.py /runner/source-metadata ${P}/setup.py ${L}/xmodule/setup.py ${L}/capa/setup.py ${P}/openedx/core/lib/xblock_builtin/xblock_discussion/setup.py >/dev/null && "
        ;;
    *)
        echo "usage: $0 clone | {py36|py27} {start|status|cleanup|logs}" >&2
        exit 2
        ;;
esac

NAMESPACE=py36-r2-e6-${RUNTIME}
MYSQL=${NAMESPACE}-mysql
CACHE=${NAMESPACE}-memcached
LMS=${NAMESPACE}-lms
CMS=${NAMESPACE}-cms
LMS_PORT=${PORT_BASE}00
CMS_PORT=${PORT_BASE}10
LOG_ROOT=${PY36_R2_E6_LOG_ROOT:-/tmp/py36-r2-e6-20261010}/${RUNTIME}
PYTHONPATH_VALUE=/edx/app/edxapp:/runner/source-metadata:${P}:${L}/xmodule:${L}/capa:${P}/openedx/core/lib/xblock_builtin/xblock_discussion:${L}/calc:${L}/safe_lxml:${L}/symmath:${L}/chem:${L}/dogstats

exists() { docker container inspect "$1" >/dev/null 2>&1; }
mysql_client() { docker exec -i "${MYSQL}" sh -c 'MYSQL_PWD="${MYSQL_ROOT_PASSWORD}" exec "$@"' sh "$@"; }

wait_for() {
    what=$1; shift
    tries=0
    until "$@" >/dev/null 2>&1; do
        tries=$((tries + 1))
        if [ "${tries}" -ge 300 ]; then echo "timeout waiting for ${what}" >&2; return 1; fi
        sleep 1
    done
}

service_args() {
    svc=$1
    # RES_OPTIONS: parallel A/AAAA lookups through Docker's embedded DNS
    # intermittently lose a reply and stall each MySQL connect for 5 s;
    # --dns-option is rejected for the CMS container:<lms> network mode.
    printf '%s\n' \
        --label "${LABEL}" --label "io.openedx.py36-r2.runtime=${RUNTIME}" --label "io.openedx.py36-r2.service=${svc}" \
        --platform "${PLATFORM}" --entrypoint /bin/sh --memory "${APP_MEMORY}" \
        --mount "type=bind,src=${SOURCE_ROOT},dst=${P},readonly" \
        --mount "type=bind,src=${WORKSPACE}/src,dst=/edx/src,readonly" \
        --mount "type=bind,src=${XBLOCK_ILT_SRC},dst=/edx/src/xblock-ilt,readonly" \
        --mount "type=bind,src=${ASSET_ROOT}/${RUNTIME},dst=/edx/var/edxapp/staticfiles,readonly" \
        --mount "type=bind,src=${CONFIG}/${svc}.auth.json,dst=/edx/app/edxapp/${svc}.auth.json,readonly" \
        --mount "type=bind,src=${CONFIG}/${svc}.env.json,dst=/edx/app/edxapp/${svc}.env.json,readonly" \
        --mount "type=bind,src=${SCRIPT_DIR}/py36_r2_e6_settings.py,dst=/edx/app/edxapp/py36_r2_e6_settings.py,readonly" \
        --mount "type=bind,src=${LOG_ROOT}/${svc},dst=/edx/var/log" \
        --mount type=tmpfs,dst=/edx/var/edxapp/data \
        --mount type=tmpfs,dst=/runner \
        --env-file "${MYSQL_ENV}" \
        --env "SERVICE_VARIANT=${svc}" --env DJANGO_SETTINGS_MODULE=py36_r2_e6_settings \
        --env "PYTHONPATH=${PYTHONPATH_VALUE}" --env PYTHONDONTWRITEBYTECODE=1 \
        --env "PY36_R2_E6_NAMESPACE=${NAMESPACE}" --env "PY36_R2_E6_CACHE_HOST=${CACHE}" \
        --env "PY36_R2_E6_MYSQL_HOST=${MYSQL}" \
        --env EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo --env NO_PYTHON_UNINSTALL=1 \
        --env RES_OPTIONS=single-request \
        -w "${P}"
}

start() {
    test "$(docker image inspect "${IMAGE}" --format '{{.Id}}')" = "${IMAGE_ID}"
    test "$(git -C "${SOURCE_ROOT}" rev-parse HEAD)" = "${EXPECTED_COMMIT}"
    test -z "$(git -C "${SOURCE_ROOT}" status --porcelain)"
    test -f "${DUMP}" && test -f "${MYSQL_ENV}"
    grep -qx "commit=${XBLOCK_ILT_COMMIT}" "${XBLOCK_ILT_SRC}.identity"
    grep -qx "source_commit=${EXPECTED_COMMIT}" "${ASSET_ROOT}/logs/provenance.txt"
    grep -qx "collect_${RUNTIME}_image=${IMAGE} ${IMAGE_ID}" "${ASSET_ROOT}/logs/provenance.txt"
    for c in ${MYSQL} ${CACHE} ${LMS} ${CMS}; do
        if exists "$c"; then echo "refusing to replace existing container: $c" >&2; exit 2; fi
    done
    for port in ${LMS_PORT} ${CMS_PORT}; do
        if lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then echo "port ${port} in use" >&2; exit 2; fi
    done
    mkdir -p "${LOG_ROOT}/lms/lms" "${LOG_ROOT}/lms/cms" "${LOG_ROOT}/cms/lms" "${LOG_ROOT}/cms/cms"

    docker run -d --name "${MYSQL}" --network "${NETWORK}" --label "${LABEL}" \
        --label "io.openedx.py36-r2.runtime=${RUNTIME}" --platform linux/amd64 --memory "${MYSQL_MEMORY}" \
        --mount type=tmpfs,dst=/var/lib/mysql --env-file "${MYSQL_ENV}" \
        "${MYSQL_IMAGE}" --character-set-server=utf8 --collation-server=utf8_general_ci >/dev/null
    docker run -d --name "${CACHE}" --network "${NETWORK}" --label "${LABEL}" \
        --label "io.openedx.py36-r2.runtime=${RUNTIME}" --memory 128m "${CACHE_IMAGE}" memcached -m 64 >/dev/null
    # The entrypoint runs a socket-only server for init, then the final server
    # on TCP; pinging over TCP waits for the final one.
    wait_for mysql mysql_client mysqladmin -uroot -h127.0.0.1 ping
    mysql_client mysql -uroot < "${DUMP}"

    # Runs before the servers start because runserver caches Site configuration.
    # shellcheck disable=SC2046
    docker run --rm --network "${NETWORK}" \
        --mount "type=bind,src=${SCRIPT_DIR}/r2-e6-fixture.py,dst=/edx/app/edxapp/r2_e6_fixture.py,readonly" \
        $(service_args lms) "${IMAGE}" \
        -c "${METADATA}exec ${PYTHON} manage.py lms shell -c \"exec(open('/edx/app/edxapp/r2_e6_fixture.py').read())\"" \
        > "${LOG_ROOT}/fixture.txt" 2>&1
    grep '^E6_FIXTURE_OK ' "${LOG_ROOT}/fixture.txt"

    # shellcheck disable=SC2046
    docker run -d --name "${LMS}" --network "${NETWORK}" \
        --publish "127.0.0.1:${LMS_PORT}:18000" --publish "127.0.0.1:${CMS_PORT}:18010" \
        $(service_args lms) "${IMAGE}" \
        -c "${METADATA}exec ${PYTHON} manage.py lms runserver 0.0.0.0:18000 --noreload --nostatic" >/dev/null
    # shellcheck disable=SC2046
    docker run -d --name "${CMS}" --network "container:${LMS}" \
        $(service_args cms) "${IMAGE}" \
        -c "${METADATA}exec ${PYTHON} manage.py cms runserver 0.0.0.0:18010 --noreload --nostatic" >/dev/null

    wait_for "LMS heartbeat" curl -fsS -o /dev/null -H 'Host: localhost:18000' "http://127.0.0.1:${LMS_PORT}/heartbeat"
    wait_for "CMS heartbeat" curl -fsS -o /dev/null -H 'Host: localhost:18010' "http://127.0.0.1:${CMS_PORT}/heartbeat"
    status
    echo "E6_SERVICES_STARTED runtime=${RUNTIME} lms=http://127.0.0.1:${LMS_PORT} cms=http://127.0.0.1:${CMS_PORT} netns=${LMS}"
}

status() {
    for c in ${MYSQL} ${CACHE} ${LMS} ${CMS}; do
        if exists "$c"; then
            docker inspect "$c" --format '{{.Name}} running={{.State.Running}} restarts={{.RestartCount}} image={{.Image}} source_ro={{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/edx-platform"}}{{not .RW}}{{end}}{{end}}'
        else
            echo "/$c absent"
        fi
    done
}

cleanup() {
    for c in ${CMS} ${LMS} ${CACHE} ${MYSQL}; do
        if exists "$c"; then
            test "$(docker inspect "$c" --format '{{index .Config.Labels "io.openedx.py36-r2.gate"}}')" = e6
            docker rm -f "$c" >/dev/null && echo "removed $c"
        fi
    done
}

case "${2:-}" in
    start) start ;;
    status) status ;;
    cleanup) cleanup ;;
    logs) for c in ${LMS} ${CMS}; do echo "== ${c}"; docker logs "${c}" 2>&1; done ;;
    *) echo "usage: $0 clone | {py36|py27} {start|status|cleanup|logs}" >&2; exit 2 ;;
esac
