#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
RUNTIME=${1:-}
ACTION=${2:-start}

case "${RUNTIME}" in
    py36)
        IMAGE=ltdps/edxapp:py36-r1-locked
        CONTAINER=py36-r1-p1b-discussion-rw-lms-20260803-r1
        FORUM_CONTAINER=py36-r1-p1b-discussion-rw-forum-20260803-r1
        ES_CONTAINER=py36-r1-p1b-discussion-rw-es-20260803-r1
        PORT=18137
        FORUM_PORT=44568
        ES_PORT=19237
        NAMESPACE=py36_r1_p1b_discussion_rw_py36_r1
        USERNAME=qadiscuss_py36
        EMAIL=qadiscuss_py36@example.com
        COURSE_KEY=course-v1:QA+DiscussionRW+Py36
        DISCUSSION_ID=p1b_discussion_rw_py36
        SQL_USER=p1b_discuss_py36
        SQL_PASSWORD=P1bSqlPy36R1
        MONGO_USER=p1b_comments_py36
        MONGO_PASSWORD=P1bMongoPy36R1
        COMMENTS_KEY=P1bCommentsPy36R1
        PYTHON=python
        ;;
    py27)
        IMAGE=ltdps/edxapp:py36-r1-p1b-dashboard-remediation-reviewfix-py27-20260802
        CONTAINER=py27-r1-p1b-discussion-rw-lms-20260803-r1
        FORUM_CONTAINER=py27-r1-p1b-discussion-rw-forum-20260803-r1
        ES_CONTAINER=py27-r1-p1b-discussion-rw-es-20260803-r1
        PORT=18138
        FORUM_PORT=44569
        ES_PORT=19238
        NAMESPACE=py36_r1_p1b_discussion_rw_py27_r1
        USERNAME=qadiscuss_py27
        EMAIL=qadiscuss_py27@example.com
        COURSE_KEY=course-v1:QA+DiscussionRW+Py27
        DISCUSSION_ID=p1b_discussion_rw_py27
        SQL_USER=p1b_discuss_py27
        SQL_PASSWORD=P1bSqlPy27R1
        MONGO_USER=p1b_comments_py27
        MONGO_PASSWORD=P1bMongoPy27R1
        COMMENTS_KEY=P1bCommentsPy27R1
        PYTHON=/edx/app/edxapp/venvs/edxapp/bin/python
        ;;
    *)
        echo "usage: $0 {py36|py27} [start|cleanup]" >&2
        exit 2
        ;;
esac

case "${ACTION}" in
    start|cleanup) ;;
    *)
        echo "usage: $0 {py36|py27} [start|cleanup]" >&2
        exit 2
        ;;
esac

SOURCE_INPUT=${PLATFORM_INTEGRATION_ROOT:-${SCRIPT_DIR}/../../../platform-py3-integration}
SOURCE_ROOT=$(CDPATH= cd -- "${SOURCE_INPUT}" && pwd -P)
WORKSPACE_ROOT=$(CDPATH= cd -- "${SOURCE_ROOT}/.." && pwd -P)
PROTECTED_ROOT=/Users/noahwang/workspace/hawthorn/platform
CONTROL_CONTAINER=py36-r1-p1b-dashboard-reviewfix-lms-20260802-r13
MYSQL_CONTAINER=edx.devstack.mysql
MONGO_CONTAINER=edx.devstack.mongo
NETWORK=devstack_default
FORUM_IMAGE=ltdps/forum@sha256:1f594e841dbeeb6dfad1a16ebff127e93b4db5427cdc0e28810b9828cf558d1e
ES_IMAGE=edxops/elasticsearch@sha256:27235efd307d30c82aa24baf0f6cc24b2cbc504445bb3fccd0e5c13f8c51d1bd

LOG_ROOT=${PY36_R1_DISCUSSION_LOG_ROOT:-/tmp/py36-p1b-discussion-read-write-20260803-r2/${RUNTIME}}
EVIDENCE_ROOT=${PY36_R1_DISCUSSION_EVIDENCE_ROOT:-${LOG_ROOT}/lms/discussion-evidence}
SQL_DATABASE=${NAMESPACE}_edxapp
SQL_HISTORY_DATABASE=${NAMESPACE}_csmh
MONGO_DATABASE=${NAMESPACE}_comments
MONGO_MODULESTORE_DATABASE=${NAMESPACE}_edxapp
MONGO_CONTENTSTORE_DATABASE=${NAMESPACE}_xcontent
MONGO_URI="mongodb://${MONGO_USER}:${MONGO_PASSWORD}@${MONGO_CONTAINER}:27017/${MONGO_DATABASE}?authSource=${MONGO_DATABASE}"
SEARCH_SERVER="http://${ES_CONTAINER}:9200/"
HOST_SEARCH_SERVER="http://127.0.0.1:${ES_PORT}"
FORUM_URL="http://${FORUM_CONTAINER}:4567"
HOST_FORUM_URL="http://127.0.0.1:${FORUM_PORT}"

if [ "$(basename -- "${SOURCE_ROOT}")" != "platform-py3-integration" ] || [ "${SOURCE_ROOT}" = "${PROTECTED_ROOT}" ]; then
    echo "refusing to mount a source other than platform-py3-integration: ${SOURCE_ROOT}" >&2
    exit 2
fi
case "${NAMESPACE}${SQL_DATABASE}${SQL_HISTORY_DATABASE}${MONGO_DATABASE}${MONGO_MODULESTORE_DATABASE}${MONGO_CONTENTSTORE_DATABASE}${SQL_USER}${MONGO_USER}" in
    *[!A-Za-z0-9_]*)
        echo "gate identifiers contain unsupported characters" >&2
        exit 2
        ;;
esac

case "${NAMESPACE}" in
    py36_r1_p1b_discussion_rw_py36_r1|py36_r1_p1b_discussion_rw_py27_r1) ;;
    *)
        echo "refusing cleanup outside the Discussion Read/Write namespace: ${NAMESPACE}" >&2
        exit 2
        ;;
esac

cleanup_resources() {
    cleanup_reason=$1
    cleanup_failed=0
    cleanup_root="${LOG_ROOT}/cleanup"
    mkdir -p "${cleanup_root}"

    for cleanup_container in "${CONTAINER}" "${FORUM_CONTAINER}" "${ES_CONTAINER}"; do
        if docker container inspect "${cleanup_container}" >/dev/null 2>&1; then
            docker inspect "${cleanup_container}" >"${cleanup_root}/${cleanup_container}.inspect.json" 2>&1 || cleanup_failed=1
            docker logs "${cleanup_container}" >"${cleanup_root}/${cleanup_container}.log" 2>&1 || cleanup_failed=1
            docker rm -f "${cleanup_container}" >>"${cleanup_root}/removed-containers.log" 2>&1 || cleanup_failed=1
        fi
    done

    for cleanup_volume in "${NAMESPACE}_es_data" "${NAMESPACE}_es_logs" "${NAMESPACE}_edxapp_data"; do
        if docker volume inspect "${cleanup_volume}" >/dev/null 2>&1; then
            docker volume inspect "${cleanup_volume}" >"${cleanup_root}/${cleanup_volume}.inspect.json" 2>&1 || cleanup_failed=1
            docker volume rm "${cleanup_volume}" >>"${cleanup_root}/removed-volumes.log" 2>&1 || cleanup_failed=1
        fi
    done

    if docker container inspect "${MONGO_CONTAINER}" >/dev/null 2>&1; then
        docker exec "${MONGO_CONTAINER}" mongo --quiet --host "${MONGO_CONTAINER}" --eval \
            "var target = db.getSiblingDB('${MONGO_DATABASE}'); if (target.getUser('${MONGO_USER}') !== null) { target.dropUser('${MONGO_USER}'); } target.dropDatabase();" \
            >"${cleanup_root}/mongo-comments-drop.log" 2>&1 || cleanup_failed=1
        docker exec "${MONGO_CONTAINER}" mongo --quiet --host "${MONGO_CONTAINER}" --eval \
            "db.getSiblingDB('${MONGO_MODULESTORE_DATABASE}').dropDatabase();" \
            >"${cleanup_root}/mongo-modulestore-drop.log" 2>&1 || cleanup_failed=1
        docker exec "${MONGO_CONTAINER}" mongo --quiet --host "${MONGO_CONTAINER}" --eval \
            "db.getSiblingDB('${MONGO_CONTENTSTORE_DATABASE}').dropDatabase();" \
            >"${cleanup_root}/mongo-contentstore-drop.log" 2>&1 || cleanup_failed=1
    else
        cleanup_failed=1
    fi

    if docker container inspect "${MYSQL_CONTAINER}" >/dev/null 2>&1; then
        docker exec "${MYSQL_CONTAINER}" mysql -uroot -e \
            "DROP DATABASE IF EXISTS \`${SQL_DATABASE}\`; DROP DATABASE IF EXISTS \`${SQL_HISTORY_DATABASE}\`;" \
            >"${cleanup_root}/mysql-databases-drop.log" 2>&1 || cleanup_failed=1
        cleanup_sql_user_exists=$(docker exec "${MYSQL_CONTAINER}" mysql -uroot --batch --skip-column-names -e \
            "SELECT COUNT(*) FROM mysql.user WHERE User='${SQL_USER}' AND Host='%';" 2>>"${cleanup_root}/mysql-user-drop.log" || true)
        if [ "${cleanup_sql_user_exists}" = "1" ]; then
            docker exec "${MYSQL_CONTAINER}" mysql -uroot -e \
                "DROP USER '${SQL_USER}'@'%'; FLUSH PRIVILEGES;" \
                >>"${cleanup_root}/mysql-user-drop.log" 2>&1 || cleanup_failed=1
        fi
    else
        cleanup_failed=1
    fi

    printf '%s\n' \
        "cleanup_reason=${cleanup_reason}" \
        "runtime=${RUNTIME}" \
        "namespace=${NAMESPACE}" \
        "cleanup_failed=${cleanup_failed}" \
        >"${cleanup_root}/cleanup-summary.txt"
    return "${cleanup_failed}"
}

if [ "${ACTION}" = "cleanup" ]; then
    cleanup_resources manual
    exit $?
fi

for candidate in "${CONTAINER}" "${FORUM_CONTAINER}" "${ES_CONTAINER}"; do
    if docker container inspect "${candidate}" >/dev/null 2>&1; then
        echo "refusing to replace existing candidate container: ${candidate}" >&2
        exit 2
    fi
done
for candidate_volume in "${NAMESPACE}_es_data" "${NAMESPACE}_es_logs" "${NAMESPACE}_edxapp_data"; do
    if docker volume inspect "${candidate_volume}" >/dev/null 2>&1; then
        echo "refusing to reuse existing candidate volume: ${candidate_volume}" >&2
        exit 2
    fi
done
for candidate_port in "${PORT}" "${FORUM_PORT}" "${ES_PORT}"; do
    if curl -fsS --connect-timeout 1 "http://127.0.0.1:${candidate_port}/" >/dev/null 2>&1; then
        echo "refusing to use occupied candidate port: ${candidate_port}" >&2
        exit 2
    fi
done

AUTH_JSON=$(docker inspect "${CONTROL_CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/lms.auth.json"}}{{.Source}}{{end}}{{end}}')
ENV_JSON=$(docker inspect "${CONTROL_CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/lms.env.json"}}{{.Source}}{{end}}{{end}}')
test -r "${AUTH_JSON}"
test -r "${ENV_JSON}"

if [ -e "${LOG_ROOT}" ]; then
    echo "refusing to overwrite an existing evidence root: ${LOG_ROOT}" >&2
    exit 2
fi
mkdir -p \
    "${LOG_ROOT}/lms/cms" \
    "${LOG_ROOT}/lms/lms" \
    "${LOG_ROOT}/forum" \
    "${LOG_ROOT}/elasticsearch" \
    "${EVIDENCE_ROOT}"
RESOURCE_LEDGER="${LOG_ROOT}/resource-ledger.txt"

MYSQL_DATABASES=$(docker exec "${MYSQL_CONTAINER}" mysql -uroot --batch --skip-column-names -e \
    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME IN ('${SQL_DATABASE}', '${SQL_HISTORY_DATABASE}');")
if [ -n "${MYSQL_DATABASES}" ]; then
    echo "refusing to reuse existing MySQL schema: ${MYSQL_DATABASES}" >&2
    exit 2
fi
MYSQL_USER_EXISTS=$(docker exec "${MYSQL_CONTAINER}" mysql -uroot --batch --skip-column-names -e \
    "SELECT COUNT(*) FROM mysql.user WHERE User='${SQL_USER}' AND Host='%';")
if [ "${MYSQL_USER_EXISTS}" != "0" ]; then
    echo "refusing to reuse existing MySQL user: ${SQL_USER}@%" >&2
    exit 2
fi

for candidate_mongo_database in "${MONGO_DATABASE}" "${MONGO_MODULESTORE_DATABASE}" "${MONGO_CONTENTSTORE_DATABASE}"; do
    MONGO_DATABASE_EXISTS=$(docker exec "${MONGO_CONTAINER}" mongo --quiet --host "${MONGO_CONTAINER}" --eval \
        "db.adminCommand({listDatabases: 1}).databases.some(function(item) { return item.name === '${candidate_mongo_database}'; })" | tail -n 1)
    if [ "${MONGO_DATABASE_EXISTS}" = "true" ]; then
        echo "refusing to reuse existing Mongo database: ${candidate_mongo_database}" >&2
        exit 2
    fi
done
MONGO_USER_EXISTS=$(docker exec "${MONGO_CONTAINER}" mongo --quiet --host "${MONGO_CONTAINER}" --eval \
    "db.getSiblingDB('${MONGO_DATABASE}').getUser('${MONGO_USER}') !== null" | tail -n 1)
if [ "${MONGO_USER_EXISTS}" = "true" ]; then
    echo "refusing to reuse existing Mongo user: ${MONGO_USER}" >&2
    exit 2
fi

CLEANUP_ARMED=1
cleanup_on_exit() {
    cleanup_exit_code=$?
    trap - EXIT INT TERM HUP
    if [ "${cleanup_exit_code}" -ne 0 ] && [ "${CLEANUP_ARMED}" = "1" ]; then
        cleanup_resources startup-failure || true
    fi
    exit "${cleanup_exit_code}"
}
trap cleanup_on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

docker exec "${MYSQL_CONTAINER}" mysql -uroot -e \
    "CREATE DATABASE \`${SQL_DATABASE}\` CHARACTER SET utf8 COLLATE utf8_general_ci;
     CREATE DATABASE \`${SQL_HISTORY_DATABASE}\` CHARACTER SET utf8 COLLATE utf8_general_ci;
     GRANT ALL PRIVILEGES ON \`${SQL_DATABASE}\`.* TO '${SQL_USER}'@'%' IDENTIFIED BY '${SQL_PASSWORD}';
     GRANT ALL PRIVILEGES ON \`${SQL_HISTORY_DATABASE}\`.* TO '${SQL_USER}'@'%';
     FLUSH PRIVILEGES;"
printf '%s\n' "mysql_database=${SQL_DATABASE}" "mysql_database=${SQL_HISTORY_DATABASE}" "mysql_user=${SQL_USER}@%" >>"${RESOURCE_LEDGER}"

docker exec "${MONGO_CONTAINER}" mongo --quiet --host "${MONGO_CONTAINER}" --eval \
    "var target = db.getSiblingDB('${MONGO_DATABASE}'); target.createUser({user: '${MONGO_USER}', pwd: '${MONGO_PASSWORD}', roles: [{role: 'readWrite', db: '${MONGO_DATABASE}'}]});"
printf '%s\n' "mongo_database=${MONGO_DATABASE}" "mongo_user=${MONGO_USER}" >>"${RESOURCE_LEDGER}"
printf '%s\n' "mongo_database=${MONGO_MODULESTORE_DATABASE}" "mongo_database=${MONGO_CONTENTSTORE_DATABASE}" >>"${RESOURCE_LEDGER}"

docker volume create "${NAMESPACE}_es_data" >/dev/null
printf '%s\n' "volume=${NAMESPACE}_es_data" >>"${RESOURCE_LEDGER}"
docker volume create "${NAMESPACE}_es_logs" >/dev/null
printf '%s\n' "volume=${NAMESPACE}_es_logs" >>"${RESOURCE_LEDGER}"
docker volume create "${NAMESPACE}_edxapp_data" >/dev/null
printf '%s\n' "volume=${NAMESPACE}_edxapp_data" >>"${RESOURCE_LEDGER}"

docker run -d \
    --name "${ES_CONTAINER}" \
    --platform linux/amd64 \
    --network "${NETWORK}" \
    --label io.openedx.py36-r1.gate=p1b-discussion-read-write \
    --label "io.openedx.py36-r1.runtime=${RUNTIME}" \
    --label "io.openedx.py36-r1.namespace=${NAMESPACE}" \
    --publish "127.0.0.1:${ES_PORT}:9200" \
    --mount "type=volume,src=${NAMESPACE}_es_data,dst=/usr/share/elasticsearch/data" \
    --mount "type=volume,src=${NAMESPACE}_es_logs,dst=/usr/share/elasticsearch/logs" \
    "${ES_IMAGE}" elasticsearch >/dev/null
printf '%s\n' "container=${ES_CONTAINER}" >>"${RESOURCE_LEDGER}"

wait_for_http() {
    url=$1
    label=$2
    output=$3
    attempt=0
    while [ "${attempt}" -lt 120 ]; do
        status=$(curl -sS --connect-timeout 2 --max-time 5 -o "${output}" -w '%{http_code}' "${url}" || true)
        if [ "${status}" = "200" ]; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    echo "${label} did not become healthy: ${url}" >&2
    test ! -r "${output}" || sed -n '1,80p' "${output}" >&2
    exit 1
}

wait_for_http "${HOST_SEARCH_SERVER}/_cluster/health" "Elasticsearch" "${EVIDENCE_ROOT}/elasticsearch-health.json"
content_index_status=$(curl -sS --connect-timeout 2 --max-time 10 \
    -X PUT \
    -o "${EVIDENCE_ROOT}/elasticsearch-content-index.json" \
    -w '%{http_code}' \
    "${HOST_SEARCH_SERVER}/content")
if [ "${content_index_status}" != "200" ]; then
    echo "failed to create the gate-owned Elasticsearch content index: HTTP ${content_index_status}" >&2
    sed -n '1,80p' "${EVIDENCE_ROOT}/elasticsearch-content-index.json" >&2
    exit 1
fi
printf '%s\n' "elasticsearch_index=content" >>"${RESOURCE_LEDGER}"

docker run -d \
    --name "${FORUM_CONTAINER}" \
    --platform linux/amd64 \
    --entrypoint /bin/bash \
    --network "${NETWORK}" \
    --label io.openedx.py36-r1.gate=p1b-discussion-read-write \
    --label "io.openedx.py36-r1.runtime=${RUNTIME}" \
    --label "io.openedx.py36-r1.namespace=${NAMESPACE}" \
    --publish "127.0.0.1:${FORUM_PORT}:4567" \
    "${FORUM_IMAGE}" -lc \
    "source /edx/app/forum/ruby_env && source /edx/app/forum/devstack_forum_env && export MONGOHQ_URL='mongodb://${MONGO_USER}:${MONGO_PASSWORD}@${MONGO_CONTAINER}:27017/${MONGO_DATABASE}?authSource=${MONGO_DATABASE}' SEARCH_SERVER='${SEARCH_SERVER}' API_KEY='${COMMENTS_KEY}' && cd /edx/app/forum/cs_comments_service && bundle install --path /edx/app/forum/.gem && exec ruby app.rb -o 0.0.0.0" >/dev/null
printf '%s\n' "container=${FORUM_CONTAINER}" >>"${RESOURCE_LEDGER}"

wait_for_http "${HOST_FORUM_URL}/heartbeat" "comments service" "${EVIDENCE_ROOT}/forum-heartbeat.json"
if ! jq -e '.OK == true' "${EVIDENCE_ROOT}/forum-heartbeat.json" >/dev/null 2>&1; then
    echo "comments service heartbeat did not report OK=true" >&2
    sed -n '1,80p' "${EVIDENCE_ROOT}/forum-heartbeat.json" >&2
    exit 1
fi

COMMON_PYTHONPATH=/edx/app/edxapp:/opt/runner:/runner/source-metadata:/edx/app/edxapp/edx-platform:/edx/app/edxapp/edx-platform/common/lib/xmodule:/edx/app/edxapp/edx-platform/common/lib/capa:/edx/app/edxapp/edx-platform/openedx/core/lib/xblock_builtin/xblock_discussion:/edx/app/edxapp/edx-platform/common/lib/calc:/edx/app/edxapp/edx-platform/common/lib/safe_lxml:/edx/app/edxapp/edx-platform/common/lib/symmath:/edx/app/edxapp/edx-platform/common/lib/chem:/edx/app/edxapp/edx-platform/common/lib/dogstats
START_COMMAND="${PYTHON} /opt/runner/py27_source_metadata.py /runner/source-metadata /edx/app/edxapp/edx-platform/setup.py /edx/app/edxapp/edx-platform/common/lib/xmodule/setup.py /edx/app/edxapp/edx-platform/common/lib/capa/setup.py /edx/app/edxapp/edx-platform/openedx/core/lib/xblock_builtin/xblock_discussion/setup.py && touch /edx/var/log/source-metadata-ready && while [ ! -f /edx/var/log/start-lms ]; do sleep 1; done && export PYTHONPATH=${COMMON_PYTHONPATH} && exec ${PYTHON} -c 'import os; from openedx.core.lib.logsettings import log_python_warnings; log_python_warnings(); from safe_lxml import defuse_xml_libs; defuse_xml_libs(); import django; django.setup(); from xblock.core import XBlock; XBlock.load_class(\"discussion\"); from django.core.management import execute_from_command_line; execute_from_command_line([\"manage.py\", \"runserver\", \"0.0.0.0:18000\", \"--noreload\"])'"

docker run -d \
    --name "${CONTAINER}" \
    --entrypoint /bin/sh \
    --network "${NETWORK}" \
    --label io.openedx.py36-r1.gate=p1b-discussion-read-write \
    --label "io.openedx.py36-r1.runtime=${RUNTIME}" \
    --label "io.openedx.py36-r1.namespace=${NAMESPACE}" \
    --publish "127.0.0.1:${PORT}:18000" \
    --mount "type=bind,src=${SOURCE_ROOT},dst=/edx/app/edxapp/edx-platform,readonly" \
    --mount "type=bind,src=${WORKSPACE_ROOT}/src,dst=/edx/src,readonly" \
    --mount "type=bind,src=${AUTH_JSON},dst=/edx/app/edxapp/lms.auth.json,readonly" \
    --mount "type=bind,src=${ENV_JSON},dst=/edx/app/edxapp/lms.env.json,readonly" \
    --mount "type=bind,src=${SCRIPT_DIR}/py27_source_metadata.py,dst=/opt/runner/py27_source_metadata.py,readonly" \
    --mount "type=bind,src=${SCRIPT_DIR}/p1b_discussion_rw_browser_settings.py,dst=/edx/app/edxapp/p1b_discussion_rw_browser_settings.py,readonly" \
    --mount "type=bind,src=${SCRIPT_DIR}/provision-p1b-discussion-read-write.py,dst=/edx/app/edxapp/provision-p1b-discussion-read-write.py,readonly" \
    --mount "type=bind,src=${LOG_ROOT}/lms,dst=/edx/var/log" \
    --mount "type=volume,src=devstack_edxapp_lms_assets,dst=/edx/var/edxapp/staticfiles,readonly" \
    --mount "type=volume,src=${NAMESPACE}_edxapp_data,dst=/edx/var/edxapp/data" \
    --env SERVICE_VARIANT=lms \
    --env DJANGO_SETTINGS_MODULE=p1b_discussion_rw_browser_settings \
    --env "PYTHONPATH=${COMMON_PYTHONPATH}" \
    --env "PY36_R1_DISCUSSION_RUNTIME=${RUNTIME}" \
    --env "PY36_R1_DISCUSSION_USERNAME=${USERNAME}" \
    --env "PY36_R1_DISCUSSION_EMAIL=${EMAIL}" \
    --env "PY36_R1_DISCUSSION_COURSE_KEY=${COURSE_KEY}" \
    --env "PY36_R1_DISCUSSION_ID=${DISCUSSION_ID}" \
    --env "PY36_R1_DISCUSSION_NAMESPACE=${NAMESPACE}" \
    --env "PY36_R1_DISCUSSION_SITE_DOMAIN=localhost:${PORT}" \
    --env "PY36_R1_DISCUSSION_SQL_DATABASE=${SQL_DATABASE}" \
    --env "PY36_R1_DISCUSSION_SQL_HISTORY_DATABASE=${SQL_HISTORY_DATABASE}" \
    --env "PY36_R1_DISCUSSION_SQL_USER=${SQL_USER}" \
    --env "PY36_R1_DISCUSSION_SQL_PASSWORD=${SQL_PASSWORD}" \
    --env "PY36_R1_DISCUSSION_MONGO_URI=${MONGO_URI}" \
    --env "PY36_R1_DISCUSSION_SEARCH_SERVER=${SEARCH_SERVER}" \
    --env "PY36_R1_DISCUSSION_EVIDENCE_DIR=/edx/var/log/discussion-evidence" \
    --env "COMMENTS_SERVICE_URL=${FORUM_URL}" \
    --env "COMMENTS_SERVICE_KEY=${COMMENTS_KEY}" \
    --env EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo \
    --env NO_PYTHON_UNINSTALL=1 \
    "${IMAGE}" -c "${START_COMMAND}" >/dev/null
printf '%s\n' "container=${CONTAINER}" >>"${RESOURCE_LEDGER}"

metadata_attempt=0
while [ ! -f "${LOG_ROOT}/lms/source-metadata-ready" ] && [ "${metadata_attempt}" -lt 60 ]; do
    if [ "$(docker inspect -f '{{.State.Running}}' "${CONTAINER}")" != "true" ]; then
        echo "LMS container exited before source metadata was ready" >&2
        docker logs "${CONTAINER}" >&2 || true
        exit 1
    fi
    metadata_attempt=$((metadata_attempt + 1))
    sleep 1
done
if [ ! -f "${LOG_ROOT}/lms/source-metadata-ready" ]; then
    echo "LMS source metadata did not become ready" >&2
    exit 1
fi

run_lms_command() {
    command_name=$1
    shift
    command_log="${LOG_ROOT}/lms/manage-${command_name}.log"
    if ! docker exec "${CONTAINER}" /bin/sh -lc \
        "cd /edx/app/edxapp/edx-platform && ${PYTHON} manage.py lms ${command_name} $*" \
        >"${command_log}" 2>&1; then
        cat "${command_log}" >&2
        return 1
    fi
    cat "${command_log}"
}

# The LMS heartbeat queries django_site, so the empty gate schema must be
# migrated before heartbeat can be used as the readiness check.
run_lms_command migrate --noinput
touch "${LOG_ROOT}/lms/start-lms"
wait_for_http "http://127.0.0.1:${PORT}/heartbeat" "LMS" "${EVIDENCE_ROOT}/lms-heartbeat.html"
run_lms_command check

if ! docker exec "${CONTAINER}" /bin/sh -lc \
    "cd /edx/app/edxapp/edx-platform && ${PYTHON} /edx/app/edxapp/provision-p1b-discussion-read-write.py provision" \
    >"${LOG_ROOT}/lms/provision.log" 2>&1; then
    cat "${LOG_ROOT}/lms/provision.log" >&2
    exit 1
fi
cat "${LOG_ROOT}/lms/provision.log"
if ! docker exec "${CONTAINER}" /bin/sh -lc \
    "cd /edx/app/edxapp/edx-platform && ${PYTHON} /edx/app/edxapp/provision-p1b-discussion-read-write.py reset" \
    >"${LOG_ROOT}/lms/preflight.log" 2>&1; then
    cat "${LOG_ROOT}/lms/preflight.log" >&2
    exit 1
fi
cat "${LOG_ROOT}/lms/preflight.log"

CLEANUP_ARMED=0
printf '%s\n' \
    "SERVICE_STARTED runtime=${RUNTIME}" \
    "lms_container=${CONTAINER} lms_url=http://127.0.0.1:${PORT}" \
    "forum_container=${FORUM_CONTAINER} forum_url=${HOST_FORUM_URL}" \
    "elasticsearch_container=${ES_CONTAINER} elasticsearch_url=${HOST_SEARCH_SERVER}" \
    "namespace=${NAMESPACE} sql_database=${SQL_DATABASE} mongo_database=${MONGO_DATABASE}" \
    "platform_mount=${SOURCE_ROOT} platform_mount_readonly=true"
