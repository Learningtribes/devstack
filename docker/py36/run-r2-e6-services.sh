#!/bin/sh
# R2-preview E6: per-runtime LMS + Studio on private MySQL, Mongo and
# Elasticsearch clones, memcached and, with PY36_R2_E6_WITH_FORUM=1, an empty
# private comments service; with PY36_R2_E6_WITH_BROKER=1, a private RabbitMQ
# and a grade/progress worker. PY36_R2_E6_PRESTART="<file.py> <evidence-dir> [args]"
# runs a `script` after the clones are loaded and before the servers start.
# usage: run-r2-e6-services.sh {clone|clone-es}
#        run-r2-e6-services.sh {py36|py27} {start|status|cleanup|logs|script <file.py> <evidence-dir> [args]}
#
# `clone` takes one read-only mysqldump of the shared edxapp/edxapp_csmh
# databases, one mongodump of the shared `edxapp` Mongo database and one
# GET-only export of the shared Elasticsearch indices (`clone-es` alone redoes
# the last); every runtime stack loads the same snapshots into its own servers.
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
ASSET_ROOT=${PY36_R2_E6_ASSET_ROOT:-/tmp/py36-r2-e6-assets-20261010-r4}
MONGO_DUMP=${CONFIG}/e6-mongo-snapshot.archive
ES_DUMP=${CONFIG}/e6-es-snapshot.json
MYSQL_IMAGE=mysql:5.6
CACHE_IMAGE=memcached@sha256:ec8ffdf1f1d2b4d7a20ac91359520528fe4a934453f8e058eaf41ac5f7f9e226
# Same images as edx.devstack.mongo / edx.devstack.elasticsearch.
MONGO_IMAGE=mongo@sha256:6a0061a32c34bc8004ed69c9d9331a0695bda9430e24bea7fb4b331864394d7f
ES_IMAGE=edxops/elasticsearch@sha256:27235efd307d30c82aa24baf0f6cc24b2cbc504445bb3fccd0e5c13f8c51d1bd
FORUM_IMAGE=ltdps/forum@sha256:1f594e841dbeeb6dfad1a16ebff127e93b4db5427cdc0e28810b9828cf558d1e
# Opt-in so group 1 keeps running with the discussion service off.
WITH_FORUM=${PY36_R2_E6_WITH_FORUM:-0}
FORUM_ENV=${CONFIG}/e6-forum.env
# Opt-in: a private RabbitMQ plus a grade/progress worker; the LMS side turns
# eager Celery off.
WITH_BROKER=${PY36_R2_E6_WITH_BROKER:-0}
BROKER_ENV=${CONFIG}/e6-broker.env
RABBIT_IMAGE=rabbitmq@sha256:4206c16c09a58d0a604668e91227c32f4a222368e796bfb7bf2e0d0d160ef97a
# Python 2.7 only, opt-in: PY36_R2_E6_ORA2_SOURCE is a clean checkout of
# ORA2_SOURCE_COMMIT (the ORA2 the Python 3.6 image installs), mounted
# read-only ahead of the image's editable edx-ora2 on PYTHONPATH, as the test
# runner does. Its setup.py and requirements equal those of the installed
# 4fcfa234, so the installed ora2 metadata (entry points, requirements) holds.
ORA2_SOURCE=${PY36_R2_E6_ORA2_SOURCE:-}
ORA2_SOURCE_COMMIT=d3f24a9c539528e960c8dcc9aef200cea0c49baf
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
    # Modulestore and contentstore live in `edxapp`; the comments service
    # database is not cloned (the gate forum starts empty).
    docker exec edx.devstack.mongo mongodump --quiet --db edxapp --archive > "${MONGO_DUMP}.tmp"
    mv "${MONGO_DUMP}.tmp" "${MONGO_DUMP}"
    echo "E6_MONGO_CLONE_DONE bytes=$(wc -c < "${MONGO_DUMP}" | tr -d ' ') sha256=$(shasum -a 256 "${MONGO_DUMP}" | cut -d' ' -f1)"
    clone_es
}

# GET-only read of the shared cluster.
clone_es() {
    umask 077
    python3 "${SCRIPT_DIR}/r2-e6-es-clone.py" dump edx.devstack.elasticsearch "${ES_DUMP}.tmp"
    mv "${ES_DUMP}.tmp" "${ES_DUMP}"
    echo "E6_ES_CLONE_DONE bytes=$(wc -c < "${ES_DUMP}" | tr -d ' ') sha256=$(shasum -a 256 "${ES_DUMP}" | cut -d' ' -f1)"
}

if [ "${1:-}" = clone ]; then clone; exit 0; fi
if [ "${1:-}" = clone-es ]; then clone_es; exit 0; fi

RUNTIME=${1:-}
case "${RUNTIME}" in
    py36)
        IMAGE=ltdps/edxapp:py36-r2-20261009
        IMAGE_ID=sha256:f02cf5e79316295694dff8e5248b8704fcd1866fb8b651bef9384c7b395aec37
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
        echo "usage: $0 clone | {py36|py27} {start|status|cleanup|logs|script <file.py> <evidence-dir> [args]}" >&2
        exit 2
        ;;
esac
# The asset tree was collected with the base runtime image.
ASSET_IMAGE=${IMAGE}
ASSET_IMAGE_ID=${IMAGE_ID}
# Python 3.6 only, opt-in: Dockerfile.r2-ora2-runtime, the base runtime plus
# the R1 ORA2 gate's edx-submissions Python 3 patch (Python files only, so the
# collected assets still apply).
ORA2_RUNTIME_IMAGE=ltdps/edxapp:py36-r2-ora2-20261010
ORA2_RUNTIME_IMAGE_ID=sha256:7f1bf1cd7be236362aff6ee97af595de0b4b16155ba02235495c73495be97022

NAMESPACE=py36-r2-e6-${RUNTIME}
MYSQL=${NAMESPACE}-mysql
MONGO=${NAMESPACE}-mongo
ES=${NAMESPACE}-es
FORUM=${NAMESPACE}-forum
FORUM_URL=http://${FORUM}:4567
CACHE=${NAMESPACE}-memcached
LMS=${NAMESPACE}-lms
CMS=${NAMESPACE}-cms
RABBIT=${NAMESPACE}-rabbitmq
WORKER=${NAMESPACE}-worker
LMS_PORT=${PORT_BASE}00
CMS_PORT=${PORT_BASE}10
STACK="${MYSQL} ${MONGO} ${ES} ${FORUM} ${RABBIT} ${CACHE} ${LMS} ${CMS} ${WORKER}"
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
        --mount "type=bind,src=${SCRIPT_DIR}/r2_e6_wsgi.py,dst=/edx/app/edxapp/r2_e6_wsgi.py,readonly" \
        --mount "type=bind,src=${LOG_ROOT}/${svc},dst=/edx/var/log" \
        --mount type=tmpfs,dst=/edx/var/edxapp/data \
        --mount type=tmpfs,dst=/runner \
        --env-file "${MYSQL_ENV}" \
        --env "SERVICE_VARIANT=${svc}" --env DJANGO_SETTINGS_MODULE=py36_r2_e6_settings \
        --env "PYTHONPATH=${PYTHONPATH_VALUE}" --env PYTHONDONTWRITEBYTECODE=1 \
        --env "PY36_R2_E6_NAMESPACE=${NAMESPACE}" --env "PY36_R2_E6_CACHE_HOST=${CACHE}" \
        --env "PY36_R2_E6_MYSQL_HOST=${MYSQL}" \
        --env "PY36_R2_E6_MONGO_HOST=${MONGO}" --env "PY36_R2_E6_ES_HOST=${ES}" \
        --env "EDXAPP_TEST_MONGO_HOST=${MONGO}" --env NO_PYTHON_UNINSTALL=1 \
        --env RES_OPTIONS=single-request \
        -w "${P}"
    if [ "${WITH_FORUM}" = 1 ]; then
        printf '%s\n' --env-file "${FORUM_ENV}" --env "PY36_R2_E6_FORUM_URL=${FORUM_URL}" \
            --env "COMMENTS_SERVICE_URL=${FORUM_URL}"
    fi
    if [ "${WITH_BROKER}" = 1 ] && [ "${svc}" = lms ]; then
        printf '%s\n' --env-file "${BROKER_ENV}" --env "PY36_R2_E6_RABBIT_HOST=${RABBIT}"
    fi
    if [ -n "${ORA2_SOURCE}" ]; then
        printf '%s\n' --mount "type=bind,src=${ORA2_SOURCE},dst=/runner/edx-ora2,readonly"
    fi
}

es_isolated() {
    nodes=$(docker exec "${ES}" curl -fsS 'http://localhost:9200/_cat/nodes?h=ip' | wc -l | tr -d ' ')
    name=$(docker exec "${ES}" curl -fsS http://localhost:9200/ | sed -n 's/.*"cluster_name" *: *"\([^"]*\)".*/\1/p')
    if [ "${nodes}" != 1 ] || [ "${name}" != "${ES}" ]; then
        echo "private elasticsearch is not isolated: nodes=${nodes} cluster=${name}" >&2
        docker stop "${ES}" >/dev/null
        exit 1
    fi
    echo "es_isolated cluster=${name} nodes=${nodes}"
}

start() {
    test "$(docker image inspect "${IMAGE}" --format '{{.Id}}')" = "${IMAGE_ID}"
    test "$(git -C "${SOURCE_ROOT}" rev-parse HEAD)" = "${EXPECTED_COMMIT}"
    test -z "$(git -C "${SOURCE_ROOT}" status --porcelain)"
    test -f "${DUMP}" && test -f "${MYSQL_ENV}" && test -f "${MONGO_DUMP}" && test -f "${ES_DUMP}"
    grep -qx "commit=${XBLOCK_ILT_COMMIT}" "${XBLOCK_ILT_SRC}.identity"
    grep -qx "source_commit=${EXPECTED_COMMIT}" "${ASSET_ROOT}/logs/provenance.txt"
    grep -qx "collect_${RUNTIME}_image=${ASSET_IMAGE} ${ASSET_IMAGE_ID}" "${ASSET_ROOT}/logs/provenance.txt"
    for c in ${STACK}; do
        if exists "$c"; then echo "refusing to replace existing container: $c" >&2; exit 2; fi
    done
    if [ "${WITH_FORUM}" = 1 ] && [ ! -f "${FORUM_ENV}" ]; then
        (umask 077; key=$(openssl rand -hex 16); printf 'COMMENTS_SERVICE_KEY=%s\n' "${key}" > "${FORUM_ENV}")
    fi
    if [ "${WITH_BROKER}" = 1 ] && [ ! -f "${BROKER_ENV}" ]; then
        (umask 077; pw=$(openssl rand -hex 16)
         printf 'PY36_R2_E6_RABBIT_USER=py36r2e6\nPY36_R2_E6_RABBIT_PASSWORD=%s\n' "${pw}" > "${BROKER_ENV}")
    fi
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
    # No --auth: the settings overlay drops the Mongo credentials.
    docker run -d --name "${MONGO}" --network "${NETWORK}" --label "${LABEL}" \
        --label "io.openedx.py36-r2.runtime=${RUNTIME}" --platform linux/amd64 --memory 1g \
        --mount type=tmpfs,dst=/data/db "${MONGO_IMAGE}" \
        mongod --smallfiles --nojournal --storageEngine wiredTiger --wiredTigerCacheSizeGB 1 >/dev/null
    # ES 1.5 multicast-discovers any default-named node on the network: without
    # these flags this node joins edx.devstack.elasticsearch's cluster and every
    # read and write lands in the shared indices.
    docker run -d --name "${ES}" --network "${NETWORK}" --label "${LABEL}" \
        --label "io.openedx.py36-r2.runtime=${RUNTIME}" --platform linux/amd64 --memory 1g \
        --env ES_HEAP_SIZE=384m "${ES_IMAGE}" elasticsearch \
        "-Des.cluster.name=${ES}" -Des.discovery.zen.ping.multicast.enabled=false >/dev/null
    wait_for mongo docker exec "${MONGO}" mongo --quiet --eval 'quit(db.adminCommand({ping: 1}).ok ? 0 : 1)'
    docker exec -i "${MONGO}" mongorestore --quiet --archive < "${MONGO_DUMP}"
    wait_for elasticsearch docker exec "${ES}" curl -fsS http://localhost:9200/
    es_isolated
    python3 "${SCRIPT_DIR}/r2-e6-es-clone.py" restore "${ES}" "${ES_DUMP}" > "${LOG_ROOT}/es-restore.txt"
    if [ "${WITH_FORUM}" = 1 ]; then
        # The comments service searches `content` but does not create it.
        docker exec "${ES}" curl -fsS -X PUT http://localhost:9200/content > "${LOG_ROOT}/es-content-index.json"
        # API_KEY is re-exported after devstack_forum_env, which sets its own.
        docker run -d --name "${FORUM}" --network "${NETWORK}" --label "${LABEL}" \
            --label "io.openedx.py36-r2.runtime=${RUNTIME}" --platform linux/amd64 --memory 1g \
            --env-file "${FORUM_ENV}" --entrypoint /bin/bash "${FORUM_IMAGE}" -lc \
            "source /edx/app/forum/ruby_env && source /edx/app/forum/devstack_forum_env && export MONGOHQ_URL=mongodb://${MONGO}:27017/cs_comments_service SEARCH_SERVER=http://${ES}:9200 API_KEY=\"\${COMMENTS_SERVICE_KEY}\" && cd /edx/app/forum/cs_comments_service && bundle install --local --path /edx/app/forum/.gem && exec ruby app.rb -o 0.0.0.0" >/dev/null
        wait_for forum sh -c "docker exec '${ES}' curl -fsS '${FORUM_URL}/heartbeat' | grep -q '\"OK\":true'"
        docker exec "${ES}" curl -fsS "${FORUM_URL}/heartbeat" > "${LOG_ROOT}/forum-heartbeat.json"
    fi
    if [ "${WITH_BROKER}" = 1 ]; then
        # The fixture below already runs with eager Celery off.
        (. "${BROKER_ENV}"
         docker run -d --name "${RABBIT}" --network "${NETWORK}" --label "${LABEL}" \
            --label "io.openedx.py36-r2.runtime=${RUNTIME}" --memory 512m \
            --env "RABBITMQ_DEFAULT_USER=${PY36_R2_E6_RABBIT_USER}" \
            --env "RABBITMQ_DEFAULT_PASS=${PY36_R2_E6_RABBIT_PASSWORD}" \
            --env "RABBITMQ_DEFAULT_VHOST=${NAMESPACE}" "${RABBIT_IMAGE}" >/dev/null)
        # As root, a CLI call that wins the race with the server creates a
        # root-owned .erlang.cookie and the server dies with eacces.
        wait_for rabbitmq docker exec -u rabbitmq "${RABBIT}" rabbitmq-diagnostics -q check_running
    fi
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
    # A gate whose provisioning changes SiteConfiguration runs it here: the
    # servers keep the configuration of each Site they have already served.
    if [ -n "${PY36_R2_E6_PRESTART:-}" ]; then
        # shellcheck disable=SC2086
        if ! run_script ${PY36_R2_E6_PRESTART} > "${LOG_ROOT}/prestart.txt" 2>&1; then
            tail -n 40 "${LOG_ROOT}/prestart.txt" >&2
            exit 1
        fi
    fi

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
    if [ "${WITH_BROKER}" = 1 ]; then
        # Shares the LMS log mount, so scripts read its log at /edx/var/log/worker.log.
        # shellcheck disable=SC2046
        docker run -d --name "${WORKER}" --network "${NETWORK}" \
            --mount "type=bind,src=${SCRIPT_DIR}/r2_e6_grading_worker.py,dst=/opt/r2-scripts/r2_e6_grading_worker.py,readonly" \
            --env "PY36_R2_E6_WORKER_HOSTNAME=${WORKER}" \
            $(service_args lms) "${IMAGE}" \
            -c "${METADATA}exec ${PYTHON} /opt/r2-scripts/r2_e6_grading_worker.py > /edx/var/log/worker.log 2>&1" >/dev/null
        wait_for "worker ready" grep -q '^PY36_R2_E6_WORKER_READY ' "${LOG_ROOT}/lms/worker.log"
    fi
    status
    echo "E6_SERVICES_STARTED runtime=${RUNTIME} lms=http://127.0.0.1:${LMS_PORT} cms=http://127.0.0.1:${CMS_PORT} netns=${LMS}"
}

status() {
    for c in ${STACK}; do
        if exists "$c"; then
            docker inspect "$c" --format '{{.Name}} running={{.State.Running}} restarts={{.RestartCount}} image={{.Image}} source_ro={{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/edx-platform"}}{{not .RW}}{{end}}{{end}}'
        else
            echo "/$c absent"
        fi
    done
}

cleanup() {
    for c in ${WORKER} ${CMS} ${LMS} ${CACHE} ${RABBIT} ${FORUM} ${ES} ${MONGO} ${MYSQL}; do
        if exists "$c"; then
            test "$(docker inspect "$c" --format '{{index .Config.Labels "io.openedx.py36-r2.gate"}}')" = e6
            # -v: the RabbitMQ, ES and Mongo images declare anonymous volumes.
            docker rm -f -v "$c" >/dev/null && echo "removed $c"
        fi
    done
}

# Runs <file.py> (relative to this directory) with the mounts, settings and
# environment of the LMS container, or of Studio with PY36_R2_E6_SCRIPT_SERVICE=cms;
# <evidence-dir> is mounted writable at /edx/var/r2-evidence. Extra environment
# comes from the space-separated files in PY36_R2_E6_SCRIPT_ENV_FILE.
run_script() {
    script=$1 evidence=$2; shift 2
    svc=${PY36_R2_E6_SCRIPT_SERVICE:-lms}
    case "${svc}" in lms|cms) ;; *) echo "PY36_R2_E6_SCRIPT_SERVICE must be lms or cms" >&2; return 2 ;; esac
    test -f "${SCRIPT_DIR}/${script}"
    mkdir -p "${evidence}"
    extra=
    for env_file in ${PY36_R2_E6_SCRIPT_ENV_FILE:-}; do extra="${extra} --env-file ${env_file}"; done
    # shellcheck disable=SC2046,SC2086
    docker run --rm --network "${NETWORK}" \
        --mount "type=bind,src=${SCRIPT_DIR},dst=/opt/r2-scripts,readonly" \
        --mount "type=bind,src=${evidence},dst=/edx/var/r2-evidence" \
        $(service_args "${svc}") ${extra} "${IMAGE}" \
        -c "${METADATA}exec ${PYTHON} /opt/r2-scripts/${script} $*"
}

# A running stack keeps the forum, broker and ORA2 source modes it was started with.
if [ "${2:-}" != start ] && exists "${FORUM}"; then WITH_FORUM=1; fi
if [ "${2:-}" != start ] && exists "${RABBIT}"; then WITH_BROKER=1; fi
ORA2_RUNTIME=${PY36_R2_E6_ORA2_RUNTIME:-0}
if [ "${2:-}" != start ] && exists "${LMS}"; then
    ORA2_SOURCE=$(docker inspect "${LMS}" --format '{{range .Mounts}}{{if eq .Destination "/runner/edx-ora2"}}{{.Source}}{{end}}{{end}}')
    if [ "$(docker inspect "${LMS}" --format '{{.Image}}')" = "${ORA2_RUNTIME_IMAGE_ID}" ]; then ORA2_RUNTIME=1; else ORA2_RUNTIME=0; fi
fi
if [ "${ORA2_RUNTIME}" = 1 ]; then
    if [ "${RUNTIME}" != py36 ]; then echo "PY36_R2_E6_ORA2_RUNTIME is py36 only" >&2; exit 2; fi
    IMAGE=${ORA2_RUNTIME_IMAGE}
    IMAGE_ID=${ORA2_RUNTIME_IMAGE_ID}
fi
if [ -n "${ORA2_SOURCE}" ]; then
    if [ "${RUNTIME}" != py27 ] ||
       [ "$(git -C "${ORA2_SOURCE}" rev-parse HEAD)" != "${ORA2_SOURCE_COMMIT}" ] ||
       [ -n "$(git -C "${ORA2_SOURCE}" status --porcelain)" ]; then
        echo "PY36_R2_E6_ORA2_SOURCE must be a clean ${ORA2_SOURCE_COMMIT} checkout (py27 only): ${ORA2_SOURCE}" >&2
        exit 2
    fi
    PYTHONPATH_VALUE=/edx/app/edxapp:/runner/source-metadata:/runner/edx-ora2:${PYTHONPATH_VALUE#/edx/app/edxapp:/runner/source-metadata:}
fi

case "${2:-}" in
    start) start ;;
    status) status ;;
    cleanup) cleanup ;;
    logs)
        for c in ${LMS} ${CMS}; do echo "== ${c}"; docker logs "${c}" 2>&1; done
        if [ -f "${LOG_ROOT}/lms/worker.log" ]; then echo "== ${WORKER}"; cat "${LOG_ROOT}/lms/worker.log"; fi
        ;;
    script) shift 2; run_script "$@" ;;
    *) echo "usage: $0 clone | {py36|py27} {start|status|cleanup|logs|script <file.py> <evidence-dir> [args]}" >&2; exit 2 ;;
esac
