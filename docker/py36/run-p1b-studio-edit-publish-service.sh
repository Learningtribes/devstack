#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
RUNTIME=${1:-}
ACTION=${2:-start}

case "${RUNTIME}" in
    py36)
        IMAGE=ltdps/edxapp@sha256:08d4d0452a3fde20f557ddca5c77aac7e1eb78c7fb4dee6e9b855b96d872152f
        PLATFORM=linux/arm64
        CMS_CONTAINER=py36-r1-p1b-studio-publish-cms-20260803-r11
        LMS_CONTAINER=py36-r1-p1b-studio-publish-lms-20260803-r11
        CACHE_CONTAINER=py36-r1-p1b-studio-publish-cache-20260803-r11
        CMS_PORT=18141
        LMS_PORT=18142
        NAMESPACE=py36_r1_p1b_studio_publish_py36_r1
        AUTHOR=qastudio_py36
        AUTHOR_EMAIL=qastudio_py36@example.com
        LEARNER=qastudiolearner_py36
        LEARNER_EMAIL=qastudiolearner_py36@example.com
        COURSE_KEY=course-v1:QA+StudioPublish+Py36
        SQL_USER=p1b_studio_py36
        SQL_PASSWORD=P1bSqlStudioPy36R1
        MONGO_USER=p1b_studio_py36
        MONGO_PASSWORD=P1bMongoStudioPy36R1
        AUTHOR_PASSWORD=P1bAuthorStudioPy36R1
        LEARNER_PASSWORD=P1bLearnerStudioPy36R1
        SECRET_KEY=P1bStudioSecretPy36R1-8a1d5c7f
        PYTHON=python
        LOG_ROOT_DEFAULT=/tmp/py36-p1b-studio-edit-publish-20260803-r30
        CONTROL_CONTAINER=py36-r1-p1b-dashboard-reviewfix-lms-20260802-r13
        ;;
    py27)
        IMAGE=ltdps/edxapp@sha256:cbeaca65ae3b7ec1a10d2438088d442af9fdedabf392b12a308f53c2acfa55cb
        PLATFORM=linux/amd64
        CMS_CONTAINER=py27-r1-p1b-studio-publish-cms-20260803-r12
        LMS_CONTAINER=py27-r1-p1b-studio-publish-lms-20260803-r12
        CACHE_CONTAINER=py27-r1-p1b-studio-publish-cache-20260803-r12
        CMS_PORT=18143
        LMS_PORT=18144
        NAMESPACE=py36_r1_p1b_studio_publish_py27_r1
        AUTHOR=qastudio_py27
        AUTHOR_EMAIL=qastudio_py27@example.com
        LEARNER=qastudiolearner_py27
        LEARNER_EMAIL=qastudiolearner_py27@example.com
        COURSE_KEY=course-v1:QA+StudioPublish+Py27
        SQL_USER=p1b_studio_py27
        SQL_PASSWORD=P1bSqlStudioPy27R1
        MONGO_USER=p1b_studio_py27
        MONGO_PASSWORD=P1bMongoStudioPy27R1
        AUTHOR_PASSWORD=P1bAuthorStudioPy27R1
        LEARNER_PASSWORD=P1bLearnerStudioPy27R1
        SECRET_KEY=P1bStudioSecretPy27R1-3f2a9c81
        PYTHON=/edx/app/edxapp/venvs/edxapp/bin/python
        LOG_ROOT_DEFAULT=/tmp/py36-p1b-studio-edit-publish-20260803-r31
        CONTROL_CONTAINER=py27-r1-p1b-dashboard-reviewfix-lms-20260802-r9
        ;;
    *)
        echo "usage: $0 {py36|py27} {start|migrate|check|provision|preflight|reset|midcondition|postflight|cleanup|status}" >&2
        exit 2
        ;;
esac

case "${ACTION}" in
    start|migrate|check|provision|preflight|reset|midcondition|postflight|cleanup|status) ;;
    *) echo "usage: $0 {py36|py27} {start|migrate|check|provision|preflight|reset|midcondition|postflight|cleanup|status}" >&2; exit 2 ;;
esac

NETWORK=devstack_default
MYSQL_CONTAINER=edx.devstack.mysql
MONGO_CONTAINER=edx.devstack.mongo
CACHE_IMAGE=memcached@sha256:ec8ffdf1f1d2b4d7a20ac91359520528fe4a934453f8e058eaf41ac5f7f9e226
CACHE_PLATFORM=linux/arm64
SOURCE_INPUT=${PLATFORM_INTEGRATION_ROOT:-${SCRIPT_DIR}/../../../platform-py3-integration}
SOURCE_ROOT=$(CDPATH= cd -- "${SOURCE_INPUT}" && pwd -P)
WORKSPACE_ROOT=$(CDPATH= cd -- "${SOURCE_ROOT}/.." && pwd -P)
PROTECTED_ROOT=/Users/noahwang/workspace/hawthorn/platform
ASSET_STAGE_ROOT=${PY36_R1_STUDIO_ASSET_STAGE_ROOT:-/tmp/py36-p1b-studio-edit-publish-assets-20260803-r10}
ASSET_RUNTIME_ROOT=${ASSET_STAGE_ROOT}/${RUNTIME}
LMS_ASSETS=${ASSET_RUNTIME_ROOT}/lms
STUDIO_ASSETS=${ASSET_RUNTIME_ROOT}/studio
LOG_ROOT=${PY36_R1_STUDIO_LOG_ROOT:-${LOG_ROOT_DEFAULT}}
EVIDENCE_DIR=${LOG_ROOT}/studio-evidence
DATA_VOLUME=${NAMESPACE}_edxapp_data
SQL_DATABASE=${NAMESPACE}_edxapp
SQL_HISTORY_DATABASE=${NAMESPACE}_csmh
MONGO_MODULESTORE_DATABASE=${NAMESPACE}_edxapp
MONGO_CONTENTSTORE_DATABASE=${NAMESPACE}_xcontent
CMS_ROOT_URL=http://localhost:${CMS_PORT}
LMS_ROOT_URL=http://localhost:${LMS_PORT}
LMS_INTERNAL_ROOT_URL=http://${LMS_CONTAINER}:18000
ASSET_CONTAINER_DIR=/edx/var/edxapp/staticfiles
COMMON_PYTHONPATH=/edx/app/edxapp:/edx/app/edxapp/edx-platform:/edx/app/edxapp/edx-platform/common/lib/xmodule:/edx/app/edxapp/edx-platform/common/lib/capa:/edx/app/edxapp/edx-platform/common/lib/calc:/edx/app/edxapp/edx-platform/common/lib/safe_lxml:/edx/app/edxapp/edx-platform/common/lib/symmath:/edx/app/edxapp/edx-platform/common/lib/chem:/edx/app/edxapp/edx-platform/common/lib/dogstats

case "${SOURCE_ROOT}" in
    */platform-py3-integration) ;;
    *) echo "refusing source outside platform-py3-integration: ${SOURCE_ROOT}" >&2; exit 2 ;;
esac
if [ "${SOURCE_ROOT}" = "${PROTECTED_ROOT}" ]; then
    echo "refusing protected Platform source" >&2
    exit 2
fi
case "${NAMESPACE}${SQL_DATABASE}${SQL_HISTORY_DATABASE}${MONGO_MODULESTORE_DATABASE}${MONGO_CONTENTSTORE_DATABASE}${SQL_USER}${MONGO_USER}${DATA_VOLUME}" in
    *[!A-Za-z0-9_]*) echo "gate identifier contains unsupported characters" >&2; exit 2 ;;
esac
case "${NAMESPACE}" in
    py36_r1_p1b_studio_publish_py36_r1|py36_r1_p1b_studio_publish_py27_r1) ;;
    *) echo "refusing cleanup outside Studio Publish namespace: ${NAMESPACE}" >&2; exit 2 ;;
esac

resource_names="${CMS_CONTAINER} ${LMS_CONTAINER} ${CACHE_CONTAINER}"
container_exists() { docker container inspect "$1" >/dev/null 2>&1; }

assert_platform_mount_readonly() {
    for container_name in "${CMS_CONTAINER}" "${LMS_CONTAINER}"; do
        if container_exists "${container_name}"; then
            source_mount=$(docker inspect "${container_name}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/edx-platform"}}{{.Source}}{{end}}{{end}}')
            source_rw=$(docker inspect "${container_name}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/edx-platform"}}{{.RW}}{{end}}{{end}}')
            asset_rw=$(docker inspect "${container_name}" --format '{{range .Mounts}}{{if eq .Destination "/edx/var/edxapp/staticfiles"}}{{.RW}}{{end}}{{end}}')
            if [ "${source_mount}" != "${SOURCE_ROOT}" ] || [ "${source_rw}" != "false" ] || [ "${asset_rw}" != "false" ]; then
                echo "read-only source/asset mount proof failed for ${container_name}: source=${source_mount} source_rw=${source_rw} asset_rw=${asset_rw}" >&2
                return 1
            fi
        fi
    done
}

cleanup_resources() {
    reason=$1
    cleanup_failed=0
    cleanup_root=${LOG_ROOT}/cleanup
    mkdir -p "${cleanup_root}"
    captured_volumes=${cleanup_root}/gate-volumes.txt
    printf '%s\n' "${DATA_VOLUME}" >"${captured_volumes}"
    for cleanup_container in ${resource_names}; do
        if container_exists "${cleanup_container}"; then
            docker inspect "${cleanup_container}" >"${cleanup_root}/${cleanup_container}.inspect.json" 2>&1 || cleanup_failed=1
            docker logs "${cleanup_container}" >"${cleanup_root}/${cleanup_container}.log" 2>&1 || cleanup_failed=1
            docker inspect "${cleanup_container}" --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{"\n"}}{{end}}{{end}}' >>"${captured_volumes}" || cleanup_failed=1
            docker rm -f "${cleanup_container}" >>"${cleanup_root}/removed-containers.log" 2>&1 || cleanup_failed=1
        fi
    done
    sort -u "${captured_volumes}" -o "${captured_volumes}"
    while IFS= read -r cleanup_volume; do
        [ -n "${cleanup_volume}" ] || continue
        if docker volume inspect "${cleanup_volume}" >/dev/null 2>&1; then
            attached_containers=$(docker ps -a --filter "volume=${cleanup_volume}" -q)
            if [ -n "${attached_containers}" ]; then
                printf '%s\n' "volume still attached: ${cleanup_volume} containers=${attached_containers}" >>"${cleanup_root}/attached-volumes.log"
                cleanup_failed=1
                continue
            fi
            docker volume inspect "${cleanup_volume}" >"${cleanup_root}/${cleanup_volume}.inspect.json" 2>&1 || cleanup_failed=1
            docker volume rm "${cleanup_volume}" >>"${cleanup_root}/removed-volumes.log" 2>&1 || cleanup_failed=1
        fi
    done <"${captured_volumes}"
    if container_exists "${MONGO_CONTAINER}"; then
        for mongo_database in "${MONGO_MODULESTORE_DATABASE}" "${MONGO_CONTENTSTORE_DATABASE}"; do
            docker exec "${MONGO_CONTAINER}" mongo --quiet --host "${MONGO_CONTAINER}" --eval \
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
        user_exists=$(docker exec "${MYSQL_CONTAINER}" mysql -uroot --batch --skip-column-names -e \
            "SELECT COUNT(*) FROM mysql.user WHERE User='${SQL_USER}' AND Host='%';" 2>>"${cleanup_root}/mysql-user-drop.log" || true)
        if [ "${user_exists}" = "1" ]; then
            docker exec "${MYSQL_CONTAINER}" mysql -uroot -e \
                "DROP USER '${SQL_USER}'@'%'; FLUSH PRIVILEGES;" >>"${cleanup_root}/mysql-user-drop.log" 2>&1 || cleanup_failed=1
        fi
    else
        cleanup_failed=1
    fi
    if [ "${reason}" = explicit-cleanup ]; then
        case "${ASSET_RUNTIME_ROOT}" in
            /tmp/py36-p1b-studio-edit-publish-assets-20260803-r2/py36|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r2/py27|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r3/py36|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r3/py27|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r4/py36|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r4/py27|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r5/py36|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r5/py27|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r6/py36|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r6/py27|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r7/py36|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r7/py27|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r8/py36|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r8/py27|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r10/py36|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r10/py27|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r11/py36|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r11/py27)
                if [ -e "${ASSET_RUNTIME_ROOT}" ]; then
                    chmod -R u+w "${ASSET_RUNTIME_ROOT}" || cleanup_failed=1
                    rm -rf "${ASSET_RUNTIME_ROOT}" || cleanup_failed=1
                fi
                ;;
            *) echo "refusing to remove unexpected asset root: ${ASSET_RUNTIME_ROOT}" >>"${cleanup_root}/asset-cleanup.log"; cleanup_failed=1 ;;
        esac
    else
        printf '%s\n' "asset_cleanup=preserved" "asset_root=${ASSET_RUNTIME_ROOT}" "reason=${reason}" >"${cleanup_root}/asset-cleanup.log"
    fi
    printf '%s\n' "cleanup_reason=${reason}" "runtime=${RUNTIME}" "namespace=${NAMESPACE}" "cleanup_failed=${cleanup_failed}" >"${cleanup_root}/cleanup-summary.txt"
    cat "${cleanup_root}/cleanup-summary.txt"
    return "${cleanup_failed}"
}

if [ "${ACTION}" = cleanup ]; then
    cleanup_resources explicit-cleanup
    exit $?
fi

if [ "${ACTION}" = status ]; then
    for status_container in ${resource_names}; do
        if container_exists "${status_container}"; then
            docker inspect "${status_container}" --format='name={{.Name}} status={{.State.Status}} running={{.State.Running}} restart={{.RestartCount}} image={{.Image}} mounts={{json .Mounts}} ports={{json .NetworkSettings.Ports}}'
        else
            echo "absent name=${status_container}"
        fi
    done
    for status_volume in "${DATA_VOLUME}"; do
        if docker volume inspect "${status_volume}" >/dev/null 2>&1; then echo "present volume=${status_volume}"; else echo "absent volume=${status_volume}"; fi
    done
    exit 0
fi

AUTH_JSON=$(docker inspect "${CONTROL_CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/lms.auth.json"}}{{.Source}}{{end}}{{end}}')
ENV_JSON=$(docker inspect "${CONTROL_CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/lms.env.json"}}{{.Source}}{{end}}{{end}}')
test -r "${AUTH_JSON}"
test -r "${ENV_JSON}"

if [ "${ACTION}" = start ]; then
    for candidate in ${resource_names}; do
        if container_exists "${candidate}"; then echo "refusing existing candidate container: ${candidate}" >&2; exit 2; fi
    done
    for candidate_port in "${CMS_PORT}" "${LMS_PORT}"; do
        if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"${candidate_port}" -sTCP:LISTEN >/dev/null 2>&1; then echo "refusing occupied port: ${candidate_port}" >&2; exit 2; fi
        if curl -sS --connect-timeout 1 --max-time 2 "http://127.0.0.1:${candidate_port}/heartbeat" >/dev/null 2>&1; then echo "refusing occupied port: ${candidate_port}" >&2; exit 2; fi
    done
    if [ -e "${LOG_ROOT}" ]; then echo "refusing existing evidence root: ${LOG_ROOT}" >&2; exit 2; fi
    if [ ! -d "${LMS_ASSETS}/lms" ] || [ ! -d "${STUDIO_ASSETS}/studio" ]; then echo "staged runtime assets are missing; run stage-p1b-studio-assets.sh" >&2; exit 2; fi
    for candidate_volume in "${DATA_VOLUME}"; do
        if docker volume inspect "${candidate_volume}" >/dev/null 2>&1; then echo "refusing existing candidate volume: ${candidate_volume}" >&2; exit 2; fi
    done
    mysql_databases=$(docker exec "${MYSQL_CONTAINER}" mysql -uroot --batch --skip-column-names -e \
        "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME IN ('${SQL_DATABASE}', '${SQL_HISTORY_DATABASE}');")
    if [ -n "${mysql_databases}" ]; then echo "refusing existing MySQL schemas: ${mysql_databases}" >&2; exit 2; fi
    mysql_user_exists=$(docker exec "${MYSQL_CONTAINER}" mysql -uroot --batch --skip-column-names -e \
        "SELECT COUNT(*) FROM mysql.user WHERE User='${SQL_USER}' AND Host='%';")
    if [ "${mysql_user_exists}" != 0 ]; then echo "refusing existing MySQL user: ${SQL_USER}@%" >&2; exit 2; fi
    for mongo_database in "${MONGO_MODULESTORE_DATABASE}" "${MONGO_CONTENTSTORE_DATABASE}"; do
        mongo_exists=$(docker exec "${MONGO_CONTAINER}" mongo --quiet --host "${MONGO_CONTAINER}" --eval \
            "db.adminCommand({listDatabases:1}).databases.some(function(item){return item.name === '${mongo_database}';})" | tail -n 1)
        if [ "${mongo_exists}" = true ]; then echo "refusing existing Mongo database: ${mongo_database}" >&2; exit 2; fi
        mongo_user_exists=$(docker exec "${MONGO_CONTAINER}" mongo --quiet --host "${MONGO_CONTAINER}" --eval \
            "db.getSiblingDB('${mongo_database}').getUser('${MONGO_USER}') !== null" | tail -n 1)
        if [ "${mongo_user_exists}" = true ]; then echo "refusing existing Mongo user: ${MONGO_USER}" >&2; exit 2; fi
    done
    mkdir -p "${LOG_ROOT}/cms" "${LOG_ROOT}/lms" "${EVIDENCE_DIR}" "${LOG_ROOT}/handshakes"
    RESOURCE_LEDGER=${LOG_ROOT}/resource-ledger.txt
    cleanup_armed=1
    cleanup_on_failure() {
        exit_code=$?
        trap - EXIT INT TERM HUP
        if [ "${exit_code}" -ne 0 ] && [ "${cleanup_armed}" = 1 ]; then cleanup_resources startup-failure || true; fi
        exit "${exit_code}"
    }
    trap cleanup_on_failure EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM HUP

    docker exec "${MYSQL_CONTAINER}" mysql -uroot -e \
        "CREATE DATABASE \`${SQL_DATABASE}\` CHARACTER SET utf8 COLLATE utf8_general_ci; CREATE DATABASE \`${SQL_HISTORY_DATABASE}\` CHARACTER SET utf8 COLLATE utf8_general_ci; GRANT ALL PRIVILEGES ON \`${SQL_DATABASE}\`.* TO '${SQL_USER}'@'%' IDENTIFIED BY '${SQL_PASSWORD}'; GRANT ALL PRIVILEGES ON \`${SQL_HISTORY_DATABASE}\`.* TO '${SQL_USER}'@'%'; FLUSH PRIVILEGES;"
    docker exec "${MONGO_CONTAINER}" mongo --quiet --host "${MONGO_CONTAINER}" --eval \
        "var a=db.getSiblingDB('${MONGO_MODULESTORE_DATABASE}'); a.createUser({user:'${MONGO_USER}',pwd:'${MONGO_PASSWORD}',roles:[{role:'readWrite',db:'${MONGO_MODULESTORE_DATABASE}'}]}); var b=db.getSiblingDB('${MONGO_CONTENTSTORE_DATABASE}'); b.createUser({user:'${MONGO_USER}',pwd:'${MONGO_PASSWORD}',roles:[{role:'readWrite',db:'${MONGO_CONTENTSTORE_DATABASE}'}]});" >"${LOG_ROOT}/mongo-user-create.log"
    docker volume create "${DATA_VOLUME}" >/dev/null
    printf '%s\n' "runtime=${RUNTIME}" "namespace=${NAMESPACE}" "image=${IMAGE}" "platform=${PLATFORM}" "source_root=${SOURCE_ROOT}" "source_commit=$(git -C "${SOURCE_ROOT}" rev-parse HEAD)" "source_tree=$(git -C "${SOURCE_ROOT}" rev-parse HEAD^{tree})" "mysql_database=${SQL_DATABASE}" "mysql_history_database=${SQL_HISTORY_DATABASE}" "mysql_user=${SQL_USER}@%" "mongo_module_store=${MONGO_MODULESTORE_DATABASE}" "mongo_content_store=${MONGO_CONTENTSTORE_DATABASE}" "mongo_user=${MONGO_USER}" "volume=${DATA_VOLUME}" "cms_port=${CMS_PORT}" "lms_port=${LMS_PORT}" "cms_asset_root=${STUDIO_ASSETS}" "lms_asset_root=${LMS_ASSETS}" >"${RESOURCE_LEDGER}"

    docker run -d --name "${CACHE_CONTAINER}" --platform "${CACHE_PLATFORM}" --network "${NETWORK}" \
        --label io.openedx.py36-r1.gate=p1b-studio-edit-publish \
        --label "io.openedx.py36-r1.runtime=${RUNTIME}" --label "io.openedx.py36-r1.namespace=${NAMESPACE}" \
        "${CACHE_IMAGE}" memcached -m 64 >/dev/null

    wait_for_running() {
        target=$1
        label=$2
        tries=0
        while [ "${tries}" -lt 120 ]; do
            if [ "$(docker inspect -f '{{.State.Running}}' "${target}")" = true ]; then return 0; fi
            tries=$((tries + 1)); sleep 1
        done
        echo "${label} did not become running" >&2
        docker logs "${target}" >&2 || true
        return 1
    }
    wait_for_running "${CACHE_CONTAINER}" cache

    start_service() {
        service=$1
        container=$2
        host_port=$3
        internal_port=$4
        settings_module=$5
        asset_source=$6
        log_subdir=$7
        site_id=$8
        service_variant=$9
        config_auth_destination=${service_variant}.auth.json
        config_env_destination=${service_variant}.env.json
        mkdir -p "${LOG_ROOT}/${log_subdir}/cms" "${LOG_ROOT}/${log_subdir}/lms"
        start_command="cd /edx/app/edxapp/edx-platform && export PYTHONPATH=${COMMON_PYTHONPATH} && exec ${PYTHON} -c 'import django; django.setup(); from django.core.management import execute_from_command_line; execute_from_command_line([\"manage.py\", \"runserver\", \"0.0.0.0:${internal_port}\", \"--noreload\"])'"
        docker run -d --name "${container}" --entrypoint /bin/sh --platform "${PLATFORM}" --network "${NETWORK}" \
            --label io.openedx.py36-r1.gate=p1b-studio-edit-publish \
            --label "io.openedx.py36-r1.runtime=${RUNTIME}" --label "io.openedx.py36-r1.namespace=${NAMESPACE}" \
            --publish "127.0.0.1:${host_port}:${internal_port}" \
            --mount "type=bind,src=${SOURCE_ROOT},dst=/edx/app/edxapp/edx-platform,readonly" \
            --mount "type=bind,src=${WORKSPACE_ROOT}/src,dst=/edx/src,readonly" \
            --mount "type=bind,src=${AUTH_JSON},dst=/edx/app/edxapp/${config_auth_destination},readonly" \
            --mount "type=bind,src=${ENV_JSON},dst=/edx/app/edxapp/${config_env_destination},readonly" \
            --mount "type=bind,src=${SCRIPT_DIR}/p1b_studio_publish_settings.py,dst=/edx/app/edxapp/p1b_studio_publish_settings.py,readonly" \
            --mount "type=bind,src=${SCRIPT_DIR}/p1b_studio_publish_lms_settings.py,dst=/edx/app/edxapp/p1b_studio_publish_lms_settings.py,readonly" \
            --mount "type=bind,src=${SCRIPT_DIR}/p1b_studio_publish_cms_settings.py,dst=/edx/app/edxapp/p1b_studio_publish_cms_settings.py,readonly" \
            --mount "type=bind,src=${SCRIPT_DIR}/provision-p1b-studio-edit-publish.py,dst=/edx/app/edxapp/provision-p1b-studio-edit-publish.py,readonly" \
            --mount "type=bind,src=${asset_source},dst=${ASSET_CONTAINER_DIR},readonly" \
            --mount "type=bind,src=${LOG_ROOT}/${log_subdir},dst=/edx/var/log" \
            --mount "type=volume,src=${DATA_VOLUME},dst=/edx/var/edxapp/data" \
            --env SERVICE_VARIANT="${service_variant}" --env CONFIG_ROOT=/edx/app/edxapp \
            --env SERVICE_VARIANT="${service_variant}" --env DJANGO_SETTINGS_MODULE="${settings_module}" \
            --env "PYTHONPATH=${COMMON_PYTHONPATH}" --env "PY36_R1_STUDIO_RUNTIME=${RUNTIME}" \
            --env "PY36_R1_STUDIO_NAMESPACE=${NAMESPACE}" --env "PY36_R1_STUDIO_ASSET_DIR=${ASSET_CONTAINER_DIR}" \
            --env "PY36_R1_STUDIO_DATA_DIR=/edx/var/edxapp/data" --env "PY36_R1_STUDIO_CACHE_CONTAINER=${CACHE_CONTAINER}" \
            --env "PY36_R1_STUDIO_MONGO_CONTAINER=${MONGO_CONTAINER}" --env "PY36_R1_STUDIO_MONGO_MODULESTORE_DATABASE=${MONGO_MODULESTORE_DATABASE}" \
            --env "PY36_R1_STUDIO_MONGO_CONTENTSTORE_DATABASE=${MONGO_CONTENTSTORE_DATABASE}" --env "PY36_R1_STUDIO_MONGO_USER=${MONGO_USER}" \
            --env "PY36_R1_STUDIO_MONGO_PASSWORD=${MONGO_PASSWORD}" --env "PY36_R1_STUDIO_SQL_DATABASE=${SQL_DATABASE}" \
            --env "PY36_R1_STUDIO_SQL_HISTORY_DATABASE=${SQL_HISTORY_DATABASE}" --env "PY36_R1_STUDIO_SQL_USER=${SQL_USER}" \
            --env "PY36_R1_STUDIO_SQL_PASSWORD=${SQL_PASSWORD}" --env "PY36_R1_STUDIO_CMS_ROOT_URL=${CMS_ROOT_URL}" \
            --env "PY36_R1_STUDIO_LMS_ROOT_URL=${LMS_ROOT_URL}" --env "PY36_R1_STUDIO_LMS_INTERNAL_ROOT_URL=${LMS_INTERNAL_ROOT_URL}" \
            --env "PY36_R1_STUDIO_SECRET_KEY=${SECRET_KEY}" --env "PY36_R1_STUDIO_SITE_ID_CMS=3" --env "PY36_R1_STUDIO_SITE_ID_LMS=4" \
            --env "PY36_R1_STUDIO_AUTHOR=${AUTHOR}" --env "PY36_R1_STUDIO_AUTHOR_EMAIL=${AUTHOR_EMAIL}" \
            --env "PY36_R1_STUDIO_LEARNER=${LEARNER}" --env "PY36_R1_STUDIO_LEARNER_EMAIL=${LEARNER_EMAIL}" \
            --env "PY36_R1_STUDIO_COURSE_KEY=${COURSE_KEY}" --env "PY36_R1_STUDIO_AUTHOR_PASSWORD=${AUTHOR_PASSWORD}" \
            --env "PY36_R1_STUDIO_LEARNER_PASSWORD=${LEARNER_PASSWORD}" --env "PY36_R1_STUDIO_EVIDENCE_DIR=/edx/var/log/studio-evidence" \
            --env "PY36_R1_STUDIO_SERVICE=${service}" --env "PY36_R1_STUDIO_SITE_DOMAIN=${service_variant}" \
            "${IMAGE}" -lc "${start_command}" >/dev/null
    printf '%s\n' "container=${container}" "service=${service}" "port=${host_port}" "asset_mount=${asset_source}" "source_mount_readonly=true" >>"${RESOURCE_LEDGER}"
    }

    start_service cms "${CMS_CONTAINER}" "${CMS_PORT}" 18010 p1b_studio_publish_cms_settings "${STUDIO_ASSETS}" cms 1 cms
    start_service lms "${LMS_CONTAINER}" "${LMS_PORT}" 18000 p1b_studio_publish_lms_settings "${LMS_ASSETS}" lms 2 lms
    wait_for_running "${CMS_CONTAINER}" cms
    wait_for_running "${LMS_CONTAINER}" lms
    for endpoint in "${CMS_PORT}" "${LMS_PORT}"; do
        tries=0
        while [ "${tries}" -lt 180 ]; do
            if curl -sS --connect-timeout 2 --max-time 5 -o /dev/null "http://127.0.0.1:${endpoint}/heartbeat" 2>/dev/null; then break; fi
            if [ "${tries}" -ge 179 ]; then echo "service did not answer on ${endpoint}" >&2; docker logs "${CMS_CONTAINER}" >&2 || true; docker logs "${LMS_CONTAINER}" >&2 || true; exit 1; fi
            tries=$((tries + 1)); sleep 1
        done
    done
    assert_platform_mount_readonly
    docker inspect "${CMS_CONTAINER}" "${LMS_CONTAINER}" "${CACHE_CONTAINER}" >"${LOG_ROOT}/container-inspect.json"
    cleanup_armed=0
    printf 'SERVICE_STARTED runtime=%s cms=%s lms=%s cache=%s cms_url=%s lms_url=%s namespace=%s\n' "${RUNTIME}" "${CMS_CONTAINER}" "${LMS_CONTAINER}" "${CACHE_CONTAINER}" "${CMS_ROOT_URL}" "${LMS_ROOT_URL}" "${NAMESPACE}"
    exit 0
fi

if ! container_exists "${CMS_CONTAINER}" || ! container_exists "${LMS_CONTAINER}"; then
    echo "Studio CMS/LMS service is absent" >&2
    exit 1
fi
assert_platform_mount_readonly

manage() {
    service=$1
    shift
    container=${CMS_CONTAINER}
    if [ "${service}" = lms ]; then container=${LMS_CONTAINER}; fi
    docker exec --workdir /edx/app/edxapp/edx-platform --env "PYTHONPATH=${COMMON_PYTHONPATH}" \
        "${container}" "${PYTHON}" manage.py "${service}" "$@"
}

case "${ACTION}" in
    migrate)
        manage cms migrate student --noinput
        manage cms migrate course_overviews --noinput
        manage cms migrate --noinput
        manage lms migrate --noinput
        manage cms migrate --noinput --database=student_module_history
        ;;
    check)
        manage cms check
        manage lms check
        ;;
    provision|preflight|reset|midcondition|postflight)
        attempt=${PY36_R1_STUDIO_ATTEMPT:-0}
        docker exec "${CMS_CONTAINER}" /bin/sh -lc \
            "cd /edx/app/edxapp/edx-platform && export PY36_R1_STUDIO_ATTEMPT='${attempt}' && ${PYTHON} /edx/app/edxapp/provision-p1b-studio-edit-publish.py ${ACTION}"
        ;;
esac
