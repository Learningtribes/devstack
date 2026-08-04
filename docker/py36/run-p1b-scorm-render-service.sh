#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
RUNTIME=${1:-}
ACTION=${2:-start}

case "${RUNTIME}" in
    py36)
        IMAGE=ltdps/edxapp:py36-r1-p1b-scorm-runtime-20260804-r1
        CONTAINER=py36-r1-p1b-scorm-render-lms-20260804-r4
        PORT=18147
        NAMESPACE=py36_r1_p1b_scorm_render_py36_r4
        USERNAME=qascorm_py36
        EMAIL=qascorm_py36@example.com
        COURSE_KEY=course-v1:QA+SCORMRender+Py36
        SQL_USER=p1b_scorm_p36r4
        SQL_PASSWORD=P1bSqlSCORMPy36R4
        MONGO_USER=p1b_scorm_p36r4
        MONGO_PASSWORD=P1bMongoSCORMPy36R4
        LOG_RUNTIME=py36-service-r4
        PYTHON=python
        RUNTIME_PLATFORM=linux/arm64
        ;;
    py27)
        IMAGE=ltdps/edxapp:py36-r1-p1b-scorm-py27-runtime-20260804-r1
        CONTAINER=py27-r1-p1b-scorm-render-lms-20260804-r4
        PORT=18148
        NAMESPACE=py36_r1_p1b_scorm_render_py27_r4
        USERNAME=qascorm_py27
        EMAIL=qascorm_py27@example.com
        COURSE_KEY=course-v1:QA+SCORMRender+Py27
        SQL_USER=p1b_scorm_p27r4
        SQL_PASSWORD=P1bSqlSCORMPy27R4
        MONGO_USER=p1b_scorm_p27r4
        MONGO_PASSWORD=P1bMongoSCORMPy27R4
        LOG_RUNTIME=py27-service-r4
        PYTHON=/edx/app/edxapp/venvs/edxapp/bin/python
        RUNTIME_PLATFORM=linux/amd64
        ;;
    *)
        echo "usage: $0 {py36|py27} {start|identity|provision|preflight|postflight|status|cleanup}" >&2
        exit 2
        ;;
esac

case "${ACTION}" in
    start|identity|provision|preflight|postflight|status|cleanup) ;;
    *)
        echo "usage: $0 {py36|py27} {start|identity|provision|preflight|postflight|status|cleanup}" >&2
        exit 2
        ;;
esac

NETWORK=devstack_default
MYSQL_CONTAINER=edx.devstack.mysql
MONGO_HOST_CONTAINER=edx.devstack.mongo
CONTROL_CONTAINER=py36-r1-p1b-dashboard-reviewfix-lms-20260802-r13
SOURCE_ROOT=${PLATFORM_INTEGRATION_ROOT:-/private/tmp/py36-p1b-scorm-platform-source-20260804-r2}
DEPENDENCY_SOURCE_ROOT=${PY36_R1_DEPENDENCY_SOURCE_ROOT:-/Users/noahwang/workspace/hawthorn/src}
LOG_ROOT=${PY36_R1_SCORM_LOG_ROOT:-/tmp/py36-p1b-scorm-render-20260804/${LOG_RUNTIME}}
ASSET_STAGE_ROOT=${PY36_R1_SCORM_ASSET_STAGE_ROOT:-/tmp/py36-p1b-ora2-assessment-assets-20260804-r4}
ASSET_ROOT=${ASSET_STAGE_ROOT}/${RUNTIME}/lms
EXPECTED_PLATFORM_COMMIT=ebb74746ecb0d771d4aa546475e88ee5c8f68a08
EXPECTED_PLATFORM_TREE=4ef0ecd352f79558d3339f0623de5223b3d6ff8d
SQL_DATABASE=${NAMESPACE}_edxapp
SQL_HISTORY_DATABASE=${NAMESPACE}_csmh
MONGO_MODULESTORE_DATABASE=${NAMESPACE}_edxapp
MONGO_CONTENTSTORE_DATABASE=${NAMESPACE}_xcontent
VOLUME_DATA=${NAMESPACE}_edxapp_data
VOLUME_SCORM=${NAMESPACE}_scorm_data
SCORM_FS_ROOT=/edx/var/edxapp/scorm-djpyfs

case "${NAMESPACE}${SQL_DATABASE}${SQL_HISTORY_DATABASE}${MONGO_MODULESTORE_DATABASE}${MONGO_CONTENTSTORE_DATABASE}${SQL_USER}${MONGO_USER}${VOLUME_DATA}${VOLUME_SCORM}" in
    *[!A-Za-z0-9_]* )
        echo "gate identifiers contain unsupported characters" >&2
        exit 2
        ;;
esac

case "${NAMESPACE}" in
    py36_r1_p1b_scorm_render_py36_r4|py36_r1_p1b_scorm_render_py27_r4) ;;
    *)
        echo "refusing action outside the SCORM render namespace: ${NAMESPACE}" >&2
        exit 2
        ;;
esac

container_exists() {
    docker container inspect "$1" >/dev/null 2>&1
}

assert_runtime_mounts() {
    source_rw=$(docker inspect "${CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/edx-platform"}}{{.RW}}{{end}}{{end}}')
    assets_rw=$(docker inspect "${CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/edx/var/edxapp/staticfiles"}}{{.RW}}{{end}}{{end}}')
    data_rw=$(docker inspect "${CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/edx/var/edxapp/data"}}{{.RW}}{{end}}{{end}}')
    scorm_rw=$(docker inspect "${CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/edx/var/edxapp/scorm-djpyfs"}}{{.RW}}{{end}}{{end}}')
    if [ "${source_rw}" != "false" ] || [ "${assets_rw}" != "false" ] || \
            [ "${data_rw}" != "true" ] || [ "${scorm_rw}" != "true" ]; then
        echo "unexpected runtime mounts: source=${source_rw} assets=${assets_rw} data=${data_rw} scorm=${scorm_rw}" >&2
        return 1
    fi
}

cleanup_resources() {
    cleanup_reason=$1
    cleanup_failed=0
    cleanup_root=${LOG_ROOT}/cleanup
    mkdir -p "${cleanup_root}"

    if container_exists "${CONTAINER}"; then
        docker inspect "${CONTAINER}" >"${cleanup_root}/${CONTAINER}.inspect.json" 2>&1 || cleanup_failed=1
        docker logs "${CONTAINER}" >"${cleanup_root}/${CONTAINER}.log" 2>&1 || cleanup_failed=1
        docker rm -f "${CONTAINER}" >"${cleanup_root}/removed-containers.log" 2>&1 || cleanup_failed=1
    fi

    for cleanup_volume in "${VOLUME_DATA}" "${VOLUME_SCORM}"; do
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

    if container_exists "${CONTAINER}"; then
        cleanup_failed=1
    fi
    for cleanup_volume in "${VOLUME_DATA}" "${VOLUME_SCORM}"; do
        if docker volume inspect "${cleanup_volume}" >/dev/null 2>&1; then
            cleanup_failed=1
        fi
    done
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
    if container_exists "${CONTAINER}"; then
        docker inspect "${CONTAINER}" --format='name={{.Name}} status={{.State.Status}} running={{.State.Running}} restart={{.RestartCount}} image={{.Image}} mounts={{json .Mounts}} ports={{json .NetworkSettings.Ports}}'
    else
        echo "absent name=${CONTAINER}"
    fi
    for status_volume in "${VOLUME_DATA}" "${VOLUME_SCORM}"; do
        if docker volume inspect "${status_volume}" >/dev/null 2>&1; then
            echo "present volume=${status_volume}"
        else
            echo "absent volume=${status_volume}"
        fi
    done
    exit 0
fi

if [ "${ACTION}" = "start" ]; then
    if [ ! -d "${SOURCE_ROOT}" ] || \
            [ "$(git -C "${SOURCE_ROOT}" rev-parse HEAD)" != "${EXPECTED_PLATFORM_COMMIT}" ] || \
            [ "$(git -C "${SOURCE_ROOT}" rev-parse HEAD^{tree})" != "${EXPECTED_PLATFORM_TREE}" ] || \
            [ -n "$(git -C "${SOURCE_ROOT}" status --porcelain=v1)" ]; then
        echo "refusing non-frozen, missing, or dirty Platform source: ${SOURCE_ROOT}" >&2
        exit 2
    fi
    if [ "${SOURCE_ROOT}" = "/Users/noahwang/workspace/hawthorn/platform" ] || \
            [ "${SOURCE_ROOT}" = "/Users/noahwang/workspace/hawthorn/platform-py3-integration" ]; then
        echo "refusing protected or dirty Platform worktree: ${SOURCE_ROOT}" >&2
        exit 2
    fi
    test -d "${DEPENDENCY_SOURCE_ROOT}"
    test -s "${ASSET_STAGE_ROOT}/asset-stage-ledger.txt"
    test -s "${ASSET_STAGE_ROOT}/${RUNTIME}-lms.sha256"
    test -s "${ASSET_ROOT}/bundles/Courseware.js"
    if find "${ASSET_ROOT}" -type f -perm -u+w -print -quit | grep . >/dev/null; then
        echo "refusing writable staged assets: ${ASSET_ROOT}" >&2
        exit 2
    fi

    AUTH_JSON=$(docker inspect "${CONTROL_CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/lms.auth.json"}}{{.Source}}{{end}}{{end}}')
    ENV_JSON=$(docker inspect "${CONTROL_CONTAINER}" --format '{{range .Mounts}}{{if eq .Destination "/edx/app/edxapp/lms.env.json"}}{{.Source}}{{end}}{{end}}')
    test -r "${AUTH_JSON}"
    test -r "${ENV_JSON}"
    if container_exists "${CONTAINER}"; then
        echo "refusing to replace existing candidate container: ${CONTAINER}" >&2
        exit 2
    fi
    if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
        echo "refusing occupied candidate port: ${PORT}" >&2
        exit 2
    fi
    if [ -e "${LOG_ROOT}" ]; then
        echo "refusing to overwrite existing evidence root: ${LOG_ROOT}" >&2
        exit 2
    fi
    for candidate_volume in "${VOLUME_DATA}" "${VOLUME_SCORM}"; do
        if docker volume inspect "${candidate_volume}" >/dev/null 2>&1; then
            echo "refusing to reuse existing candidate volume: ${candidate_volume}" >&2
            exit 2
        fi
    done
    mkdir -p "${LOG_ROOT}/cms" "${LOG_ROOT}/lms"
    RESOURCE_LEDGER=${LOG_ROOT}/resource-ledger.txt

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
    docker volume create "${VOLUME_SCORM}" >/dev/null
    printf '%s\n' "volume=${VOLUME_DATA}" "volume=${VOLUME_SCORM}" >>"${RESOURCE_LEDGER}"

    COMMON_PYTHONPATH=/edx/app/edxapp:/opt/runner:/runner/source-metadata:/edx/app/edxapp/edx-platform:/edx/app/edxapp/edx-platform/common/lib/xmodule:/edx/app/edxapp/edx-platform/common/lib/capa:/edx/app/edxapp/edx-platform/common/lib/calc:/edx/app/edxapp/edx-platform/common/lib/safe_lxml:/edx/app/edxapp/edx-platform/common/lib/symmath:/edx/app/edxapp/edx-platform/common/lib/chem:/edx/app/edxapp/edx-platform/common/lib/dogstats
    if [ "${RUNTIME}" = "py36" ]; then
        START_COMMAND="cd /edx/app/edxapp/edx-platform && export PYTHONPATH=${COMMON_PYTHONPATH} && touch /edx/var/log/source-metadata-ready && while [ ! -f /edx/var/log/start-lms ]; do sleep 1; done && exec python -c 'from openedx.core.lib.logsettings import log_python_warnings; log_python_warnings(); from safe_lxml import defuse_xml_libs; defuse_xml_libs(); import django; django.setup(); from django.core.management import execute_from_command_line; execute_from_command_line([\"manage.py\", \"runserver\", \"0.0.0.0:18000\", \"--noreload\"])' >> /edx/var/log/lms.log 2>&1"
    else
        START_COMMAND="cd /edx/app/edxapp/edx-platform && ${PYTHON} /opt/runner/py27_source_metadata.py /runner/source-metadata /edx/app/edxapp/edx-platform/setup.py /edx/app/edxapp/edx-platform/common/lib/xmodule/setup.py /edx/app/edxapp/edx-platform/common/lib/capa/setup.py && export PYTHONPATH=${COMMON_PYTHONPATH} && touch /edx/var/log/source-metadata-ready && while [ ! -f /edx/var/log/start-lms ]; do sleep 1; done && exec ${PYTHON} -c 'from openedx.core.lib.logsettings import log_python_warnings; log_python_warnings(); from safe_lxml import defuse_xml_libs; defuse_xml_libs(); import django; django.setup(); from django.core.management import execute_from_command_line; execute_from_command_line([\"manage.py\", \"runserver\", \"0.0.0.0:18000\", \"--noreload\"])' >> /edx/var/log/lms.log 2>&1"
    fi

    docker run -d \
        --name "${CONTAINER}" \
        --entrypoint /bin/sh \
        --platform "${RUNTIME_PLATFORM}" \
        --network "${NETWORK}" \
        --label io.openedx.py36-r1.gate=p1b-scorm-render \
        --label "io.openedx.py36-r1.runtime=${RUNTIME}" \
        --label "io.openedx.py36-r1.namespace=${NAMESPACE}" \
        --publish "127.0.0.1:${PORT}:18000" \
        --tmpfs /runner:rw,exec,size=64m \
        --mount "type=bind,src=${SOURCE_ROOT},dst=/edx/app/edxapp/edx-platform,readonly" \
        --mount "type=bind,src=${DEPENDENCY_SOURCE_ROOT},dst=/edx/src,readonly" \
        --mount "type=bind,src=${AUTH_JSON},dst=/edx/app/edxapp/lms.auth.json,readonly" \
        --mount "type=bind,src=${ENV_JSON},dst=/edx/app/edxapp/lms.env.json,readonly" \
        --mount "type=bind,src=${SCRIPT_DIR}/p1b_scorm_render_browser_settings.py,dst=/edx/app/edxapp/p1b_scorm_render_browser_settings.py,readonly" \
        --mount "type=bind,src=${SCRIPT_DIR}/provision-p1b-scorm-render.py,dst=/edx/app/edxapp/provision-p1b-scorm-render.py,readonly" \
        --mount "type=bind,src=${SCRIPT_DIR}/py27_source_metadata.py,dst=/opt/runner/py27_source_metadata.py,readonly" \
        --mount "type=bind,src=${LOG_ROOT},dst=/edx/var/log" \
        --mount "type=bind,src=${ASSET_ROOT},dst=/edx/var/edxapp/staticfiles,readonly" \
        --mount "type=volume,src=${VOLUME_DATA},dst=/edx/var/edxapp/data" \
        --mount "type=volume,src=${VOLUME_SCORM},dst=${SCORM_FS_ROOT}" \
        --env SERVICE_VARIANT=lms \
        --env DJANGO_SETTINGS_MODULE=p1b_scorm_render_browser_settings \
        --env "PYTHONPATH=${COMMON_PYTHONPATH}" \
        --env "PY36_R1_SCORM_RUNTIME=${RUNTIME}" \
        --env "PY36_R1_SCORM_USERNAME=${USERNAME}" \
        --env "PY36_R1_SCORM_EMAIL=${EMAIL}" \
        --env "PY36_R1_SCORM_COURSE_KEY=${COURSE_KEY}" \
        --env "PY36_R1_SCORM_NAMESPACE=${NAMESPACE}" \
        --env "PY36_R1_SCORM_SITE_DOMAIN=localhost:${PORT}" \
        --env "PY36_R1_SCORM_SQL_DATABASE=${SQL_DATABASE}" \
        --env "PY36_R1_SCORM_SQL_HISTORY_DATABASE=${SQL_HISTORY_DATABASE}" \
        --env "PY36_R1_SCORM_SQL_USER=${SQL_USER}" \
        --env "PY36_R1_SCORM_SQL_PASSWORD=${SQL_PASSWORD}" \
        --env "PY36_R1_SCORM_MONGO_MODULESTORE_DATABASE=${MONGO_MODULESTORE_DATABASE}" \
        --env "PY36_R1_SCORM_MONGO_CONTENTSTORE_DATABASE=${MONGO_CONTENTSTORE_DATABASE}" \
        --env "PY36_R1_SCORM_MONGO_USER=${MONGO_USER}" \
        --env "PY36_R1_SCORM_MONGO_PASSWORD=${MONGO_PASSWORD}" \
        --env "PY36_R1_SCORM_MONGO_CONTAINER=${MONGO_HOST_CONTAINER}" \
        --env "PY36_R1_SCORM_FS_ROOT=${SCORM_FS_ROOT}" \
        --env "PY36_R1_SCORM_PLATFORM_COMMIT=${EXPECTED_PLATFORM_COMMIT}" \
        --env "PY36_R1_SCORM_PLATFORM_TREE=${EXPECTED_PLATFORM_TREE}" \
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
    test -f "${LOG_ROOT}/source-metadata-ready"

    run_lms_manage() {
        manage_action=$1
        shift
        log_file=${LOG_ROOT}/manage-${manage_action}.log
        if ! docker exec "${CONTAINER}" /bin/sh -lc \
            "cd /edx/app/edxapp/edx-platform && ${PYTHON} manage.py lms ${manage_action} $*" \
            >"${log_file}" 2>&1; then
            cat "${log_file}" >&2
            return 1
        fi
        cat "${log_file}"
    }

    run_lms_manage migrate --noinput
    history_log=${LOG_ROOT}/manage-migrate-student-module-history.log
    if ! docker exec "${CONTAINER}" /bin/sh -lc \
        "cd /edx/app/edxapp/edx-platform && ${PYTHON} manage.py lms migrate --noinput --database=student_module_history" \
        >"${history_log}" 2>&1; then
        cat "${history_log}" >&2
        exit 1
    fi
    cat "${history_log}"
    run_lms_manage check

    touch "${LOG_ROOT}/start-lms"
    ready_tries=0
    while [ "${ready_tries}" -lt 90 ]; do
        login_status=$(curl -sS --connect-timeout 2 --max-time 5 -o "${LOG_ROOT}/login.html" -w '%{http_code}' "http://127.0.0.1:${PORT}/login" || true)
        if [ "${login_status}" = "200" ]; then
            break
        fi
        if [ "$(docker inspect -f '{{.State.Running}}' "${CONTAINER}")" != "true" ]; then
            echo "LMS container exited before HTTP readiness" >&2
            docker logs "${CONTAINER}" >&2 || true
            exit 1
        fi
        ready_tries=$((ready_tries + 1))
        sleep 1
    done
    if [ "${ready_tries}" -ge 90 ]; then
        echo "LMS login did not become ready" >&2
        tail -n 160 "${LOG_ROOT}/lms.log" >&2 || true
        exit 1
    fi

    assert_runtime_mounts
    printf '%s\n' \
        "source_root=${SOURCE_ROOT}" \
        "source_commit=${EXPECTED_PLATFORM_COMMIT}" \
        "source_tree=${EXPECTED_PLATFORM_TREE}" \
        "source_mount_readonly=true" \
        "asset_root=${ASSET_ROOT}" \
        "asset_mount_readonly=true" \
        "scorm_volume=${VOLUME_SCORM}" \
        "runtime=${RUNTIME}" \
        "namespace=${NAMESPACE}" \
        >>"${RESOURCE_LEDGER}"
    docker inspect "${CONTAINER}" >"${LOG_ROOT}/container-inspect.json"
    cleanup_armed=0
    echo "SERVICE_STARTED runtime=${RUNTIME} lms=${CONTAINER} url=http://localhost:${PORT} namespace=${NAMESPACE}"
    exit 0
fi

if ! container_exists "${CONTAINER}"; then
    echo "LMS container is absent: ${CONTAINER}" >&2
    exit 1
fi
assert_runtime_mounts

attempt=${PY36_R1_SCORM_ATTEMPT:-1}
case "${attempt}" in
    1|2) ;;
    *) echo "PY36_R1_SCORM_ATTEMPT must be 1 or 2" >&2; exit 2 ;;
esac
gate_command="cd /edx/app/edxapp/edx-platform && export PY36_R1_SCORM_ATTEMPT='${attempt}' && ${PYTHON} /edx/app/edxapp/provision-p1b-scorm-render.py ${ACTION}"
if [ "${ACTION}" = "preflight" ]; then
    preflight_log=${LOG_ROOT}/preflight-attempt${attempt}.log
    preflight_tmp=${preflight_log}.tmp
    if [ -e "${preflight_log}" ] || [ -e "${preflight_tmp}" ]; then
        echo "refusing to overwrite preflight evidence for attempt ${attempt}" >&2
        exit 2
    fi
    if docker exec "${CONTAINER}" /bin/sh -lc "${gate_command}" >"${preflight_tmp}" 2>&1; then
        mv "${preflight_tmp}" "${preflight_log}"
        cat "${preflight_log}"
    else
        preflight_status=$?
        cat "${preflight_tmp}" >&2
        exit "${preflight_status}"
    fi
else
    docker exec "${CONTAINER}" /bin/sh -lc "${gate_command}"
fi
