#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
RUNTIME=${1:-}
ACTION=${2:-start}

case "${RUNTIME}" in
    py36)
        IMAGE=ltdps/edxapp:py36-r1-p1b-ora2-runtime-20260804-r3
        CONTAINER=py36-r1-p1b-ora2-assessment-lms-20260804-r17
        WORKER_CONTAINER=py36-r1-p1b-ora2-assessment-worker-20260804-r17
        RABBIT_CONTAINER=py36-r1-p1b-ora2-assessment-rabbit-20260804-r17
        CACHE_CONTAINER=py36-r1-p1b-ora2-assessment-cache-20260804-r17
        PORT=18145
        NAMESPACE=py36_r1_p1b_ora2_assessment_py36_r17
        USERNAME=qaora2_py36
        EMAIL=qaora2_py36@example.com
        STAFF_USERNAME=qaora2staff_py36
        STAFF_EMAIL=qaora2staff_py36@example.com
        COURSE_KEY=course-v1:QA+ORA2Assessment+Py36
        SQL_USER=p1b_ora2_p36r17
        SQL_PASSWORD=P1bSqlORA2Py36R17
        MONGO_USER=p1b_ora2_p36r17
        MONGO_PASSWORD=P1bMongoORA2Py36R17
        RABBIT_USER=p1b_ora2_p36r17
        RABBIT_PASSWORD=P1bRabbitORA2Py36R17
        LOG_RUNTIME=py36-service-r17
        PYTHON=python
        RUNTIME_PLATFORM=linux/arm64
        ;;
    py27)
        IMAGE=ltdps/edxapp:py36-r1-p1b-ora2-py27-runtime-20260804-r1
        CONTAINER=py27-r1-p1b-ora2-assessment-lms-20260804-r2
        WORKER_CONTAINER=py27-r1-p1b-ora2-assessment-worker-20260804-r2
        RABBIT_CONTAINER=py27-r1-p1b-ora2-assessment-rabbit-20260804-r2
        CACHE_CONTAINER=py27-r1-p1b-ora2-assessment-cache-20260804-r2
        PORT=18146
        NAMESPACE=py36_r1_p1b_ora2_assessment_py27_r2
        USERNAME=qaora2_py27
        EMAIL=qaora2_py27@example.com
        STAFF_USERNAME=qaora2staff_py27
        STAFF_EMAIL=qaora2staff_py27@example.com
        COURSE_KEY=course-v1:QA+ORA2Assessment+Py27
        SQL_USER=p1b_ora2_p27r2
        SQL_PASSWORD=P1bSqlORA2Py27R2
        MONGO_USER=p1b_ora2_p27r2
        MONGO_PASSWORD=P1bMongoORA2Py27R2
        RABBIT_USER=p1b_ora2_p27r2
        RABBIT_PASSWORD=P1bRabbitORA2Py27R2
        LOG_RUNTIME=py27-service-r2
        PYTHON=/edx/app/edxapp/venvs/edxapp/bin/python
        RUNTIME_PLATFORM=linux/amd64
        ;;
    *)
        echo "usage: $0 {py36|py27} {start|cleanup|identity|provision|preflight|submission-ready|staff-lease|reset|postflight|status}" >&2
        exit 2
        ;;
esac

case "${ACTION}" in
    start|cleanup|identity|provision|preflight|submission-ready|staff-lease|reset|postflight|status) ;;
    *)
        echo "usage: $0 {py36|py27} {start|cleanup|identity|provision|preflight|submission-ready|staff-lease|reset|postflight|status}" >&2
        exit 2
        ;;
esac

NETWORK=devstack_default
MYSQL_CONTAINER=edx.devstack.mysql
MONGO_HOST_CONTAINER=edx.devstack.mongo
CONTROL_CONTAINER=py36-r1-p1b-dashboard-reviewfix-lms-20260802-r13
GIT_METADATA_ROOT=/Users/noahwang/workspace/hawthorn/platform/.git
LOG_ROOT=${PY36_R1_ORA2_LOG_ROOT:-/tmp/py36-p1b-ora2-assessment-20260804/${LOG_RUNTIME}}
ASSET_STAGE_ROOT=${PY36_R1_ORA2_ASSET_STAGE_ROOT:-/tmp/py36-p1b-ora2-assessment-assets-20260804-r4}
ASSET_ROOT=${ASSET_STAGE_ROOT}/${RUNTIME}/lms
EXPECTED_PLATFORM_COMMIT=7644241bb598ac20e20e70dd7abf2e5110f5b7bd
EXPECTED_PLATFORM_TREE=7c5e963e767bb1eaa16c9e64222694698b7727a3
SQL_DATABASE=${NAMESPACE}_edxapp
SQL_HISTORY_DATABASE=${NAMESPACE}_csmh
MONGO_MODULESTORE_DATABASE=${NAMESPACE}_edxapp
MONGO_CONTENTSTORE_DATABASE=${NAMESPACE}_xcontent
VOLUME_DATA=${NAMESPACE}_edxapp_data
RABBIT_VOLUME=${NAMESPACE}_rabbit_data
RABBIT_IMAGE=rabbitmq@sha256:4206c16c09a58d0a604668e91227c32f4a222368e796bfb7bf2e0d0d160ef97a
CACHE_IMAGE=memcached@sha256:ec8ffdf1f1d2b4d7a20ac91359520528fe4a934453f8e058eaf41ac5f7f9e226

case "${NAMESPACE}${SQL_DATABASE}${SQL_HISTORY_DATABASE}${MONGO_MODULESTORE_DATABASE}${MONGO_CONTENTSTORE_DATABASE}${SQL_USER}${MONGO_USER}${RABBIT_USER}${VOLUME_DATA}${RABBIT_VOLUME}" in
    *[!A-Za-z0-9_]* )
        echo "gate identifiers contain unsupported characters" >&2
        exit 2
        ;;
esac

case "${NAMESPACE}" in
    py36_r1_p1b_ora2_assessment_py36_r17|py36_r1_p1b_ora2_assessment_py27_r2) ;;
    *)
        echo "refusing cleanup outside the ORA2 assessment namespace: ${NAMESPACE}" >&2
        exit 2
        ;;
esac

resource_names="${CONTAINER} ${WORKER_CONTAINER} ${RABBIT_CONTAINER} ${CACHE_CONTAINER}"

container_exists() {
    docker container inspect "$1" >/dev/null 2>&1
}

assert_platform_mount_readonly() {
    for container_name in "${CONTAINER}" "${WORKER_CONTAINER}"; do
        if container_exists "${container_name}"; then
            mount_rw=$(docker inspect "${container_name}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/edx-platform"}}{{.RW}}{{end}}{{end}}')
            if [ "${mount_rw}" != "false" ]; then
                echo "Platform mount is not read-only for ${container_name}: ${mount_rw}" >&2
                return 1
            fi
        fi
    done
}

assert_runtime_mounts_readonly() {
    for container_name in "${CONTAINER}" "${WORKER_CONTAINER}"; do
        if container_exists "${container_name}"; then
            platform_rw=$(docker inspect "${container_name}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/edx-platform"}}{{.RW}}{{end}}{{end}}')
            assets_rw=$(docker inspect "${container_name}" --format '{{range .Mounts}}{{if eq .Destination "/edx/var/edxapp/staticfiles"}}{{.RW}}{{end}}{{end}}')
            git_metadata_rw=$(docker inspect "${container_name}" --format '{{range .Mounts}}{{if eq .Destination "/Users/noahwang/workspace/hawthorn/platform/.git"}}{{.RW}}{{end}}{{end}}')
            if [ "${platform_rw}" != "false" ] || [ "${assets_rw}" != "false" ] || [ "${git_metadata_rw}" != "false" ]; then
                echo "runtime source/assets/git metadata mount is not read-only for ${container_name}: source=${platform_rw} assets=${assets_rw} git_metadata=${git_metadata_rw}" >&2
                return 1
            fi
        fi
    done
}

cleanup_resources() {
    cleanup_reason=$1
    cleanup_failed=0
    cleanup_root="${LOG_ROOT}/cleanup"
    mkdir -p "${cleanup_root}"

    mounted_volumes=""
    for cleanup_container in ${resource_names}; do
        if container_exists "${cleanup_container}"; then
            docker inspect "${cleanup_container}" >"${cleanup_root}/${cleanup_container}.inspect.json" 2>&1 || cleanup_failed=1
            docker logs "${cleanup_container}" >"${cleanup_root}/${cleanup_container}.log" 2>&1 || cleanup_failed=1
            container_volumes=$(docker inspect "${cleanup_container}" --format '{{range .Mounts}}{{if eq .Type "volume"}}{{println .Name}}{{end}}{{end}}') || cleanup_failed=1
            mounted_volumes="${mounted_volumes} ${container_volumes}"
            docker rm -f "${cleanup_container}" >>"${cleanup_root}/removed-containers.log" 2>&1 || cleanup_failed=1
        fi
    done

    for cleanup_volume in ${mounted_volumes} "${VOLUME_DATA}" "${RABBIT_VOLUME}"; do
        [ -n "${cleanup_volume}" ] || continue
        case "${cleanup_volume}" in
            "${VOLUME_DATA}"|"${RABBIT_VOLUME}"|"${NAMESPACE}"_*) ;;
            *)
                echo "refusing non-gate mounted volume: ${cleanup_volume}" >>"${cleanup_root}/volume-refusals.log"
                cleanup_failed=1
                continue
                ;;
        esac
        if docker volume inspect "${cleanup_volume}" >/dev/null 2>&1; then
            docker volume inspect "${cleanup_volume}" >"${cleanup_root}/${cleanup_volume}.inspect.json" 2>&1 || cleanup_failed=1
            docker volume rm "${cleanup_volume}" >>"${cleanup_root}/removed-volumes.log" 2>&1 || cleanup_failed=1
        fi
    done

    if container_exists "${MONGO_HOST_CONTAINER}"; then
        for mongo_database in "${MONGO_MODULESTORE_DATABASE}" "${MONGO_CONTENTSTORE_DATABASE}"; do
            docker exec "${MONGO_HOST_CONTAINER}" mongo --quiet --host "${MONGO_HOST_CONTAINER}" --eval \
                "var target=db.getSiblingDB('${mongo_database}'); if (target.getUser('${MONGO_USER}') !== null) { target.dropUser('${MONGO_USER}'); } target.dropDatabase();" \
                >>"${cleanup_root}/mongo-drop.log" 2>&1 || cleanup_failed=1
        done
    else
        cleanup_failed=1
    fi

    if container_exists "${MYSQL_CONTAINER}"; then
        docker exec "${MYSQL_CONTAINER}" mysql -uroot -e \
            "DROP DATABASE IF EXISTS \`${SQL_DATABASE}\`; DROP DATABASE IF EXISTS \`${SQL_HISTORY_DATABASE}\`;" \
            >"${cleanup_root}/mysql-databases-drop.log" 2>&1 || cleanup_failed=1
        if user_exists=$(docker exec "${MYSQL_CONTAINER}" mysql -uroot --batch --skip-column-names -e \
                "SELECT COUNT(*) FROM mysql.user WHERE User='${SQL_USER}' AND Host='%';" \
                2>>"${cleanup_root}/mysql-user-drop.log"); then
            if [ "${user_exists}" = "1" ]; then
                docker exec "${MYSQL_CONTAINER}" mysql -uroot -e \
                    "DROP USER '${SQL_USER}'@'%'; FLUSH PRIVILEGES;" \
                    >>"${cleanup_root}/mysql-user-drop.log" 2>&1 || cleanup_failed=1
            fi
        else
            cleanup_failed=1
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
    cat "${cleanup_root}/cleanup-summary.txt"
    return "${cleanup_failed}"
}

if [ "${ACTION}" = "cleanup" ]; then
    cleanup_resources explicit-cleanup
    exit $?
fi

if [ "${ACTION}" = "status" ]; then
    for status_container in ${resource_names}; do
        if container_exists "${status_container}"; then
            docker inspect "${status_container}" --format='name={{.Name}} status={{.State.Status}} running={{.State.Running}} restart={{.RestartCount}} image={{.Image}} mounts={{json .Mounts}} ports={{json .NetworkSettings.Ports}}'
        else
            echo "absent name=${status_container}"
        fi
    done
    for status_volume in "${VOLUME_DATA}" "${RABBIT_VOLUME}"; do
        if docker volume inspect "${status_volume}" >/dev/null 2>&1; then
            echo "present volume=${status_volume}"
        else
            echo "absent volume=${status_volume}"
        fi
    done
    exit 0
fi

if [ "${ACTION}" = "start" ]; then
    SOURCE_INPUT=${PLATFORM_INTEGRATION_ROOT:-${SCRIPT_DIR}/../../../platform-py3-integration}
    SOURCE_ROOT=$(CDPATH= cd -- "${SOURCE_INPUT}" && pwd -P)
    DEPENDENCY_SOURCE_ROOT=${PY36_R1_DEPENDENCY_SOURCE_ROOT:-/Users/noahwang/workspace/hawthorn/src}
    PROTECTED_ROOT=/Users/noahwang/workspace/hawthorn/platform
    if [ "${SOURCE_ROOT}" = "${PROTECTED_ROOT}" ]; then
        echo "refusing protected Platform source: ${SOURCE_ROOT}" >&2
        exit 2
    fi
    if [ "$(git -C "${SOURCE_ROOT}" rev-parse HEAD)" != "${EXPECTED_PLATFORM_COMMIT}" ] || \
            [ "$(git -C "${SOURCE_ROOT}" rev-parse HEAD^{tree})" != "${EXPECTED_PLATFORM_TREE}" ] || \
            [ -n "$(git -C "${SOURCE_ROOT}" status --porcelain=v1)" ]; then
        echo "refusing non-frozen or dirty Platform source: ${SOURCE_ROOT}" >&2
        exit 2
    fi
    if [ "$(git -C "${SOURCE_ROOT}" rev-parse --git-common-dir)" != "${GIT_METADATA_ROOT}" ] || \
            [ ! -d "${GIT_METADATA_ROOT}" ]; then
        echo "frozen Platform worktree git metadata is unavailable: ${GIT_METADATA_ROOT}" >&2
        exit 2
    fi
    if [ ! -d "${DEPENDENCY_SOURCE_ROOT}" ]; then
        echo "dependency source root is missing: ${DEPENDENCY_SOURCE_ROOT}" >&2
        exit 2
    fi
    case "${ASSET_STAGE_ROOT}" in
        /tmp/py36-p1b-ora2-assessment-assets-20260804-r[1-9]|/tmp/py36-p1b-ora2-assessment-assets-20260804-r[1-9][0-9]) ;;
        *) echo "refusing asset stage outside the ORA2 gate root: ${ASSET_STAGE_ROOT}" >&2; exit 2 ;;
    esac
    test -s "${ASSET_STAGE_ROOT}/asset-stage-ledger.txt"
    test -s "${ASSET_STAGE_ROOT}/${RUNTIME}-lms.sha256"
    test -s "${ASSET_ROOT}/bundles/Courseware.js"
    test -s "${ASSET_ROOT}/xblock/resources/openassessment.xblock/static/js/openassessment-lms.min.js"
    if find "${ASSET_ROOT}" -type f -perm -u+w -print -quit | grep . >/dev/null; then
        echo "refusing writable staged assets: ${ASSET_ROOT}" >&2
        exit 2
    fi
    AUTH_JSON=$(docker inspect "${CONTROL_CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/lms.auth.json"}}{{.Source}}{{end}}{{end}}')
    ENV_JSON=$(docker inspect "${CONTROL_CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/lms.env.json"}}{{.Source}}{{end}}{{end}}')
    test -r "${AUTH_JSON}"
    test -r "${ENV_JSON}"

    for candidate in ${resource_names}; do
        if container_exists "${candidate}"; then
            echo "refusing to replace existing candidate container: ${candidate}" >&2
            exit 2
        fi
    done
    if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
        echo "refusing occupied candidate port: ${PORT}" >&2
        exit 2
    fi
    if curl -sS --connect-timeout 1 --max-time 2 "http://127.0.0.1:${PORT}/heartbeat" >/dev/null 2>&1; then
        echo "refusing occupied candidate port: ${PORT}" >&2
        exit 2
    fi
    if [ -e "${LOG_ROOT}" ]; then
        echo "refusing to overwrite existing evidence root: ${LOG_ROOT}" >&2
        exit 2
    fi
    for candidate_volume in "${VOLUME_DATA}" "${RABBIT_VOLUME}"; do
        if docker volume inspect "${candidate_volume}" >/dev/null 2>&1; then
            echo "refusing to reuse existing candidate volume: ${candidate_volume}" >&2
            exit 2
        fi
    done
    mkdir -p "${LOG_ROOT}/ora2-evidence" "${LOG_ROOT}/cms" "${LOG_ROOT}/lms"
    RESOURCE_LEDGER="${LOG_ROOT}/resource-ledger.txt"

    mysql_databases=$(docker exec "${MYSQL_CONTAINER}" mysql -uroot --batch --skip-column-names -e \
        "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME IN ('${SQL_DATABASE}', '${SQL_HISTORY_DATABASE}');")
    if [ -n "${mysql_databases}" ]; then
        echo "refusing to reuse existing MySQL schema: ${mysql_databases}" >&2
        exit 2
    fi
    mysql_user_exists=$(docker exec "${MYSQL_CONTAINER}" mysql -uroot --batch --skip-column-names -e \
        "SELECT COUNT(*) FROM mysql.user WHERE User='${SQL_USER}' AND Host='%';")
    if [ "${mysql_user_exists}" != "0" ]; then
        echo "refusing to reuse existing MySQL user: ${SQL_USER}@%" >&2
        exit 2
    fi

    for mongo_database in "${MONGO_MODULESTORE_DATABASE}" "${MONGO_CONTENTSTORE_DATABASE}"; do
        mongo_exists=$(docker exec "${MONGO_HOST_CONTAINER}" mongo --quiet --host "${MONGO_HOST_CONTAINER}" --eval \
            "db.adminCommand({listDatabases:1}).databases.some(function(item){return item.name === '${mongo_database}';})" | tail -n 1)
        if [ "${mongo_exists}" = "true" ]; then
            echo "refusing to reuse existing Mongo database: ${mongo_database}" >&2
            exit 2
        fi
        mongo_user_exists=$(docker exec "${MONGO_HOST_CONTAINER}" mongo --quiet --host "${MONGO_HOST_CONTAINER}" --eval \
            "db.getSiblingDB('${mongo_database}').getUser('${MONGO_USER}') !== null" | tail -n 1)
        if [ "${mongo_user_exists}" = "true" ]; then
            echo "refusing to reuse existing Mongo user: ${MONGO_USER}" >&2
            exit 2
        fi
    done

    cleanup_armed=1
    cleanup_on_failure() {
        exit_code=$?
        trap - EXIT INT TERM HUP
        if [ "${exit_code}" -ne 0 ] && [ "${cleanup_armed}" = "1" ]; then
            cleanup_resources startup-failure || true
        fi
        exit "${exit_code}"
    }
    trap cleanup_on_failure EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM HUP

    docker exec "${MYSQL_CONTAINER}" mysql -uroot -e \
        "CREATE DATABASE \`${SQL_DATABASE}\` CHARACTER SET utf8 COLLATE utf8_general_ci;
         CREATE DATABASE \`${SQL_HISTORY_DATABASE}\` CHARACTER SET utf8 COLLATE utf8_general_ci;
         GRANT ALL PRIVILEGES ON \`${SQL_DATABASE}\`.* TO '${SQL_USER}'@'%' IDENTIFIED BY '${SQL_PASSWORD}';
         GRANT ALL PRIVILEGES ON \`${SQL_HISTORY_DATABASE}\`.* TO '${SQL_USER}'@'%';
         FLUSH PRIVILEGES;"
    printf '%s\n' "mysql_database=${SQL_DATABASE}" "mysql_database=${SQL_HISTORY_DATABASE}" "mysql_user=${SQL_USER}@%" >>"${RESOURCE_LEDGER}"

    for mongo_database in "${MONGO_MODULESTORE_DATABASE}" "${MONGO_CONTENTSTORE_DATABASE}"; do
        docker exec "${MONGO_HOST_CONTAINER}" mongo --quiet --host "${MONGO_HOST_CONTAINER}" --eval \
            "var target=db.getSiblingDB('${mongo_database}'); target.createUser({user:'${MONGO_USER}',pwd:'${MONGO_PASSWORD}',roles:[{role:'readWrite',db:'${mongo_database}'}]});" \
            >>"${LOG_ROOT}/mongo-user-create.log"
        printf '%s\n' "mongo_database=${mongo_database}" "mongo_user=${MONGO_USER}" >>"${RESOURCE_LEDGER}"
    done

    docker volume create "${VOLUME_DATA}" >/dev/null
    docker volume create "${RABBIT_VOLUME}" >/dev/null
    printf '%s\n' "volume=${VOLUME_DATA}" "volume=${RABBIT_VOLUME}" >>"${RESOURCE_LEDGER}"

    docker run -d \
        --name "${RABBIT_CONTAINER}" \
        --platform linux/arm64 \
        --network "${NETWORK}" \
        --label io.openedx.py36-r1.gate=p1b-ora2-assessment \
        --label "io.openedx.py36-r1.runtime=${RUNTIME}" \
        --label "io.openedx.py36-r1.namespace=${NAMESPACE}" \
        --mount "type=volume,src=${RABBIT_VOLUME},dst=/var/lib/rabbitmq" \
        --env RABBITMQ_DEFAULT_USER="${RABBIT_USER}" \
        --env RABBITMQ_DEFAULT_PASS="${RABBIT_PASSWORD}" \
        --env RABBITMQ_DEFAULT_VHOST="${NAMESPACE}" \
        "${RABBIT_IMAGE}" >/dev/null
    printf '%s\n' "container=${RABBIT_CONTAINER}" "broker_vhost=${NAMESPACE}" >>"${RESOURCE_LEDGER}"

    docker run -d \
        --name "${CACHE_CONTAINER}" \
        --platform linux/arm64 \
        --network "${NETWORK}" \
        --label io.openedx.py36-r1.gate=p1b-ora2-assessment \
        --label "io.openedx.py36-r1.runtime=${RUNTIME}" \
        --label "io.openedx.py36-r1.namespace=${NAMESPACE}" \
        "${CACHE_IMAGE}" memcached -m 64 >/dev/null
    printf '%s\n' "container=${CACHE_CONTAINER}" "cache_endpoint=${CACHE_CONTAINER}:11211" >>"${RESOURCE_LEDGER}"

    wait_for_container() {
        target=$1
        label=$2
        tries=0
        while [ "${tries}" -lt 90 ]; do
            if [ "$(docker inspect -f '{{.State.Running}}' "${target}")" = "true" ]; then
                return 0
            fi
            tries=$((tries + 1))
            sleep 1
        done
        echo "${label} did not become running" >&2
        docker logs "${target}" >&2 || true
        return 1
    }
    wait_for_container "${RABBIT_CONTAINER}" rabbitmq
    wait_for_container "${CACHE_CONTAINER}" memcached
    rabbit_tries=0
    while [ "${rabbit_tries}" -lt 90 ]; do
        if docker exec "${RABBIT_CONTAINER}" rabbitmq-diagnostics -q ping >/dev/null 2>&1; then
            break
        fi
        rabbit_tries=$((rabbit_tries + 1))
        sleep 1
    done
    if [ "${rabbit_tries}" -ge 90 ]; then
        echo "RabbitMQ did not become healthy" >&2
        exit 1
    fi

    COMMON_PYTHONPATH=/edx/app/edxapp:/opt/runner:/runner/source-metadata:/edx/app/edxapp/edx-platform:/edx/app/edxapp/edx-platform/common/lib/xmodule:/edx/app/edxapp/edx-platform/common/lib/capa:/edx/app/edxapp/edx-platform/common/lib/calc:/edx/app/edxapp/edx-platform/common/lib/safe_lxml:/edx/app/edxapp/edx-platform/common/lib/symmath:/edx/app/edxapp/edx-platform/common/lib/chem:/edx/app/edxapp/edx-platform/common/lib/dogstats
    if [ "${RUNTIME}" = "py36" ]; then
        SOURCE_SETUP=""
        START_COMMAND="export PYTHONPATH=${COMMON_PYTHONPATH} && touch /edx/var/log/source-metadata-ready && while [ ! -f /edx/var/log/start-lms ]; do sleep 1; done && exec python -c 'import os; from openedx.core.lib.logsettings import log_python_warnings; log_python_warnings(); from safe_lxml import defuse_xml_libs; defuse_xml_libs(); import django; django.setup(); from django.core.management import execute_from_command_line; execute_from_command_line([\"manage.py\", \"runserver\", \"0.0.0.0:18000\", \"--noreload\"])' >> /edx/var/log/lms.log 2>&1"
    else
        SOURCE_SETUP="${PYTHON} /opt/runner/py27_source_metadata.py /runner/source-metadata /edx/app/edxapp/edx-platform/setup.py /edx/app/edxapp/edx-platform/common/lib/xmodule/setup.py /edx/app/edxapp/edx-platform/common/lib/capa/setup.py && "
        START_COMMAND="${SOURCE_SETUP} touch /edx/var/log/source-metadata-ready && while [ ! -f /edx/var/log/start-lms ]; do sleep 1; done && export PYTHONPATH=${COMMON_PYTHONPATH} && exec ${PYTHON} -c 'import os; from openedx.core.lib.logsettings import log_python_warnings; log_python_warnings(); from safe_lxml import defuse_xml_libs; defuse_xml_libs(); import django; django.setup(); from django.core.management import execute_from_command_line; execute_from_command_line([\"manage.py\", \"runserver\", \"0.0.0.0:18000\", \"--noreload\"])' >> /edx/var/log/lms.log 2>&1"
    fi

    docker run -d \
        --name "${CONTAINER}" \
        --entrypoint /bin/sh \
        --platform "${RUNTIME_PLATFORM}" \
        --network "${NETWORK}" \
        --label io.openedx.py36-r1.gate=p1b-ora2-assessment \
        --label "io.openedx.py36-r1.runtime=${RUNTIME}" \
        --label "io.openedx.py36-r1.namespace=${NAMESPACE}" \
        --publish "127.0.0.1:${PORT}:18000" \
        --tmpfs /runner:rw,exec,size=64m \
        --mount "type=bind,src=${SOURCE_ROOT},dst=/edx/app/edxapp/edx-platform,readonly" \
        --mount "type=bind,src=${GIT_METADATA_ROOT},dst=${GIT_METADATA_ROOT},readonly" \
        --mount "type=bind,src=${DEPENDENCY_SOURCE_ROOT},dst=/edx/src,readonly" \
        --mount "type=bind,src=${AUTH_JSON},dst=/edx/app/edxapp/lms.auth.json,readonly" \
        --mount "type=bind,src=${ENV_JSON},dst=/edx/app/edxapp/lms.env.json,readonly" \
        --mount "type=bind,src=${SCRIPT_DIR}/p1b_ora2_assessment_browser_settings.py,dst=/edx/app/edxapp/p1b_ora2_assessment_browser_settings.py,readonly" \
        --mount "type=bind,src=${SCRIPT_DIR}/provision-p1b-ora2-assessment.py,dst=/edx/app/edxapp/provision-p1b-ora2-assessment.py,readonly" \
        --mount "type=bind,src=${SCRIPT_DIR}/py27_source_metadata.py,dst=/opt/runner/py27_source_metadata.py,readonly" \
        --mount "type=bind,src=${LOG_ROOT},dst=/edx/var/log" \
        --mount "type=bind,src=${ASSET_ROOT},dst=/edx/var/edxapp/staticfiles,readonly" \
        --mount "type=volume,src=${VOLUME_DATA},dst=/edx/var/edxapp/data" \
        --env SERVICE_VARIANT=lms \
        --env DJANGO_SETTINGS_MODULE=p1b_ora2_assessment_browser_settings \
        --env "PYTHONPATH=${COMMON_PYTHONPATH}" \
        --env "PY36_R1_ORA2_RUNTIME=${RUNTIME}" \
        --env "PY36_R1_ORA2_USERNAME=${USERNAME}" \
        --env "PY36_R1_ORA2_EMAIL=${EMAIL}" \
        --env "PY36_R1_ORA2_STAFF_USERNAME=${STAFF_USERNAME}" \
        --env "PY36_R1_ORA2_STAFF_EMAIL=${STAFF_EMAIL}" \
        --env "PY36_R1_ORA2_COURSE_KEY=${COURSE_KEY}" \
        --env "PY36_R1_ORA2_NAMESPACE=${NAMESPACE}" \
        --env "PY36_R1_ORA2_SITE_DOMAIN=localhost:${PORT}" \
        --env "PY36_R1_ORA2_SQL_DATABASE=${SQL_DATABASE}" \
        --env "PY36_R1_ORA2_SQL_HISTORY_DATABASE=${SQL_HISTORY_DATABASE}" \
        --env "PY36_R1_ORA2_SQL_USER=${SQL_USER}" \
        --env "PY36_R1_ORA2_SQL_PASSWORD=${SQL_PASSWORD}" \
        --env "PY36_R1_ORA2_MONGO_MODULESTORE_DATABASE=${MONGO_MODULESTORE_DATABASE}" \
        --env "PY36_R1_ORA2_MONGO_CONTENTSTORE_DATABASE=${MONGO_CONTENTSTORE_DATABASE}" \
        --env "PY36_R1_ORA2_MONGO_USER=${MONGO_USER}" \
        --env "PY36_R1_ORA2_MONGO_PASSWORD=${MONGO_PASSWORD}" \
        --env "PY36_R1_ORA2_MONGO_CONTAINER=${MONGO_HOST_CONTAINER}" \
        --env "PY36_R1_ORA2_RABBIT_CONTAINER=${RABBIT_CONTAINER}" \
        --env "PY36_R1_ORA2_RABBIT_USER=${RABBIT_USER}" \
        --env "PY36_R1_ORA2_RABBIT_PASSWORD=${RABBIT_PASSWORD}" \
        --env "PY36_R1_ORA2_CACHE_CONTAINER=${CACHE_CONTAINER}" \
        --env "PY36_R1_ORA2_EVIDENCE_DIR=/edx/var/log/ora2-evidence" \
        --env PY36_R1_ORA2_HANDSHAKE_DIR=/edx/var/log/handshakes \
        --env PY36_R1_ORA2_LMS_LOG=/edx/var/log/lms.log \
        --env PY36_R1_ORA2_WORKER_LOG=/edx/var/log/worker.log \
        --env EDXAPP_TEST_MONGO_HOST="${MONGO_HOST_CONTAINER}" \
        --env NO_PYTHON_UNINSTALL=1 \
        "${IMAGE}" -c "${START_COMMAND}" >/dev/null
    printf '%s\n' "container=${CONTAINER}" "port=${PORT}" >>"${RESOURCE_LEDGER}"

    metadata_tries=0
    while [ ! -f "${LOG_ROOT}/source-metadata-ready" ] && [ "${metadata_tries}" -lt 90 ]; do
        if [ "$(docker inspect -f '{{.State.Running}}' "${CONTAINER}")" != "true" ]; then
            echo "LMS container exited before source metadata was ready" >&2
            docker logs "${CONTAINER}" >&2 || true
            exit 1
        fi
        metadata_tries=$((metadata_tries + 1))
        sleep 1
    done
    if [ ! -f "${LOG_ROOT}/source-metadata-ready" ]; then
        echo "LMS source metadata did not become ready" >&2
        exit 1
    fi

    run_lms_manage() {
        manage_action=$1
        shift
        log_file="${LOG_ROOT}/manage-${manage_action}.log"
        if ! docker exec "${CONTAINER}" /bin/sh -lc \
            "cd /edx/app/edxapp/edx-platform && ${PYTHON} manage.py lms ${manage_action} $*" \
            >"${log_file}" 2>&1; then
            cat "${log_file}" >&2
            return 1
        fi
        cat "${log_file}"
    }

    run_lms_history_migrate() {
        log_file="${LOG_ROOT}/manage-migrate-student-module-history.log"
        if ! docker exec "${CONTAINER}" /bin/sh -lc \
            "cd /edx/app/edxapp/edx-platform && ${PYTHON} manage.py lms migrate --noinput --database=student_module_history" \
            >"${log_file}" 2>&1; then
            cat "${log_file}" >&2
            return 1
        fi
        cat "${log_file}"
    }

    run_lms_manage migrate --noinput
    run_lms_history_migrate
    run_lms_manage check

    touch "${LOG_ROOT}/start-lms"
    heartbeat_tries=0
    while [ "${heartbeat_tries}" -lt 90 ]; do
        heartbeat_status=$(curl -sS --connect-timeout 2 --max-time 5 -o "${LOG_ROOT}/heartbeat.html" -w '%{http_code}' "http://127.0.0.1:${PORT}/heartbeat" || true)
        case "${heartbeat_status}" in
            2??|3??|4??|5??)
                printf '%s\n' "lms_http_ready=true" "heartbeat_status=${heartbeat_status}" >>"${RESOURCE_LEDGER}"
                break
                ;;
        esac
        if [ "$(docker inspect -f '{{.State.Running}}' "${CONTAINER}")" != "true" ]; then
            echo "LMS container exited before HTTP response" >&2
            docker logs "${CONTAINER}" >&2 || true
            exit 1
        fi
        heartbeat_tries=$((heartbeat_tries + 1))
        sleep 1
    done
    if [ "${heartbeat_tries}" -ge 90 ]; then
        echo "LMS did not produce an HTTP response" >&2
        test ! -r "${LOG_ROOT}/heartbeat.html" || sed -n '1,120p' "${LOG_ROOT}/heartbeat.html" >&2
        exit 1
    fi

    if [ "${RUNTIME}" = "py27" ]; then
        WORKER_SOURCE_SETUP="${PYTHON} /opt/runner/py27_source_metadata.py /runner/source-metadata /edx/app/edxapp/edx-platform/setup.py /edx/app/edxapp/edx-platform/common/lib/xmodule/setup.py /edx/app/edxapp/edx-platform/common/lib/capa/setup.py && "
    else
        WORKER_SOURCE_SETUP=""
    fi
    WORKER_COMMAND="${WORKER_SOURCE_SETUP} export PYTHONPATH=${COMMON_PYTHONPATH} && ${PYTHON} /opt/runner/p1b_ora2_assessment_worker.py > /edx/var/log/worker.log 2>&1"
    docker run -d \
        --name "${WORKER_CONTAINER}" \
        --entrypoint /bin/sh \
        --platform "${RUNTIME_PLATFORM}" \
        --network "${NETWORK}" \
        --label io.openedx.py36-r1.gate=p1b-ora2-assessment \
        --label "io.openedx.py36-r1.runtime=${RUNTIME}" \
        --label "io.openedx.py36-r1.namespace=${NAMESPACE}" \
        --tmpfs /runner:rw,exec,size=64m \
        --mount "type=bind,src=${SOURCE_ROOT},dst=/edx/app/edxapp/edx-platform,readonly" \
        --mount "type=bind,src=${GIT_METADATA_ROOT},dst=${GIT_METADATA_ROOT},readonly" \
        --mount "type=bind,src=${DEPENDENCY_SOURCE_ROOT},dst=/edx/src,readonly" \
        --mount "type=bind,src=${AUTH_JSON},dst=/edx/app/edxapp/lms.auth.json,readonly" \
        --mount "type=bind,src=${ENV_JSON},dst=/edx/app/edxapp/lms.env.json,readonly" \
        --mount "type=bind,src=${SCRIPT_DIR}/p1b_ora2_assessment_browser_settings.py,dst=/edx/app/edxapp/p1b_ora2_assessment_browser_settings.py,readonly" \
        --mount "type=bind,src=${SCRIPT_DIR}/py27_source_metadata.py,dst=/opt/runner/py27_source_metadata.py,readonly" \
        --mount "type=bind,src=${SCRIPT_DIR}/p1b_ora2_assessment_worker.py,dst=/opt/runner/p1b_ora2_assessment_worker.py,readonly" \
        --mount "type=bind,src=${LOG_ROOT},dst=/edx/var/log" \
        --mount "type=bind,src=${ASSET_ROOT},dst=/edx/var/edxapp/staticfiles,readonly" \
        --mount "type=volume,src=${VOLUME_DATA},dst=/edx/var/edxapp/data" \
        --env SERVICE_VARIANT=lms \
        --env DJANGO_SETTINGS_MODULE=p1b_ora2_assessment_browser_settings \
        --env "PYTHONPATH=${COMMON_PYTHONPATH}" \
        --env "PY36_R1_ORA2_RUNTIME=${RUNTIME}" \
        --env "PY36_R1_ORA2_USERNAME=${USERNAME}" \
        --env "PY36_R1_ORA2_EMAIL=${EMAIL}" \
        --env "PY36_R1_ORA2_STAFF_USERNAME=${STAFF_USERNAME}" \
        --env "PY36_R1_ORA2_STAFF_EMAIL=${STAFF_EMAIL}" \
        --env "PY36_R1_ORA2_COURSE_KEY=${COURSE_KEY}" \
        --env "PY36_R1_ORA2_NAMESPACE=${NAMESPACE}" \
        --env "PY36_R1_ORA2_SITE_DOMAIN=localhost:${PORT}" \
        --env "PY36_R1_ORA2_SQL_DATABASE=${SQL_DATABASE}" \
        --env "PY36_R1_ORA2_SQL_HISTORY_DATABASE=${SQL_HISTORY_DATABASE}" \
        --env "PY36_R1_ORA2_SQL_USER=${SQL_USER}" \
        --env "PY36_R1_ORA2_SQL_PASSWORD=${SQL_PASSWORD}" \
        --env "PY36_R1_ORA2_MONGO_MODULESTORE_DATABASE=${MONGO_MODULESTORE_DATABASE}" \
        --env "PY36_R1_ORA2_MONGO_CONTENTSTORE_DATABASE=${MONGO_CONTENTSTORE_DATABASE}" \
        --env "PY36_R1_ORA2_MONGO_USER=${MONGO_USER}" \
        --env "PY36_R1_ORA2_MONGO_PASSWORD=${MONGO_PASSWORD}" \
        --env "PY36_R1_ORA2_MONGO_CONTAINER=${MONGO_HOST_CONTAINER}" \
        --env "PY36_R1_ORA2_RABBIT_CONTAINER=${RABBIT_CONTAINER}" \
        --env "PY36_R1_ORA2_RABBIT_USER=${RABBIT_USER}" \
        --env "PY36_R1_ORA2_RABBIT_PASSWORD=${RABBIT_PASSWORD}" \
        --env "PY36_R1_ORA2_CACHE_CONTAINER=${CACHE_CONTAINER}" \
        --env "PY36_R1_ORA2_EVIDENCE_DIR=/edx/var/log/ora2-evidence" \
        --env PY36_R1_ORA2_HANDSHAKE_DIR=/edx/var/log/handshakes \
        --env PY36_R1_ORA2_LMS_LOG=/edx/var/log/lms.log \
        --env "PY36_R1_ORA2_WORKER_HOSTNAME=${WORKER_CONTAINER}" \
        --env PY36_R1_ORA2_WORKER_LOG=/edx/var/log/worker.log \
        --env EDXAPP_TEST_MONGO_HOST="${MONGO_HOST_CONTAINER}" \
        --env NO_PYTHON_UNINSTALL=1 \
        "${IMAGE}" -c "${WORKER_COMMAND}" >/dev/null
    printf '%s\n' "container=${WORKER_CONTAINER}" "queues=${NAMESPACE}.grade,${NAMESPACE}.progress" >>"${RESOURCE_LEDGER}"

    worker_tries=0
    while [ "${worker_tries}" -lt 90 ]; do
        if [ "$(docker inspect -f '{{.State.Running}}' "${WORKER_CONTAINER}")" != "true" ]; then
            echo "worker exited during startup" >&2
            sed -n '1,160p' "${LOG_ROOT}/worker.log" >&2 || true
            exit 1
        fi
        if rg -q 'P1B_ORA2_WORKER_READY' "${LOG_ROOT}/worker.log" 2>/dev/null; then
            break
        fi
        worker_tries=$((worker_tries + 1))
        sleep 1
    done
    if ! rg -q 'P1B_ORA2_WORKER_READY' "${LOG_ROOT}/worker.log" 2>/dev/null; then
        echo "worker did not report readiness" >&2
        sed -n '1,200p' "${LOG_ROOT}/worker.log" >&2 || true
        exit 1
    fi
    assert_runtime_mounts_readonly
    printf '%s\n' \
        "source_root=${SOURCE_ROOT}" \
        "source_commit=${EXPECTED_PLATFORM_COMMIT}" \
        "source_tree=${EXPECTED_PLATFORM_TREE}" \
        "source_mount_readonly=true" \
        "git_metadata_root=${GIT_METADATA_ROOT}" \
        "git_metadata_mount_readonly=true" \
        "asset_root=${ASSET_ROOT}" \
        "asset_mount_readonly=true" \
        "runtime=${RUNTIME}" \
        "namespace=${NAMESPACE}" \
        >>"${RESOURCE_LEDGER}"
    docker inspect "${CONTAINER}" "${WORKER_CONTAINER}" "${RABBIT_CONTAINER}" "${CACHE_CONTAINER}" >"${LOG_ROOT}/container-inspect.json"
    cleanup_armed=0
    echo "SERVICE_STARTED runtime=${RUNTIME} lms=${CONTAINER} worker=${WORKER_CONTAINER} rabbit=${RABBIT_CONTAINER} cache=${CACHE_CONTAINER} url=http://localhost:${PORT} namespace=${NAMESPACE}"
    exit 0
fi

if ! container_exists "${CONTAINER}"; then
    echo "LMS container is absent: ${CONTAINER}" >&2
    exit 1
fi
assert_runtime_mounts_readonly
case "${ACTION}" in
    identity|provision|preflight|submission-ready|staff-lease|reset|postflight)
        attempt=${PY36_R1_ORA2_ATTEMPT:-1}
        response_marker=${PY36_R1_ORA2_RESPONSE_MARKER:-ORA2_RESPONSE_${RUNTIME}_A${attempt}}
        feedback_marker=${PY36_R1_ORA2_FEEDBACK_MARKER:-ORA2_FEEDBACK_${RUNTIME}_A${attempt}}
        gate_command="cd /edx/app/edxapp/edx-platform && export PY36_R1_ORA2_ATTEMPT='${attempt}' PY36_R1_ORA2_RESPONSE_MARKER='${response_marker}' PY36_R1_ORA2_FEEDBACK_MARKER='${feedback_marker}' && ${PYTHON} /edx/app/edxapp/provision-p1b-ora2-assessment.py ${ACTION}"
        if [ "${ACTION}" = "preflight" ]; then
            preflight_log="${LOG_ROOT}/preflight-attempt${attempt}.log"
            preflight_tmp="${preflight_log}.tmp"
            preflight_failed="${preflight_log}.failed"
            if [ -e "${preflight_log}" ] || [ -e "${preflight_tmp}" ] || [ -e "${preflight_failed}" ]; then
                echo "refusing to overwrite preflight evidence for attempt ${attempt}" >&2
                exit 2
            fi
            if docker exec "${CONTAINER}" /bin/sh -lc "${gate_command}" >"${preflight_tmp}" 2>&1; then
                mv "${preflight_tmp}" "${preflight_log}"
                cat "${preflight_log}"
            else
                preflight_status=$?
                mv "${preflight_tmp}" "${preflight_failed}"
                cat "${preflight_failed}" >&2
                exit "${preflight_status}"
            fi
        else
            docker exec "${CONTAINER}" /bin/sh -lc "${gate_command}"
        fi
        ;;
esac
