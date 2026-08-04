#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
SOURCE_INPUT=${PLATFORM_INTEGRATION_ROOT:-${SCRIPT_DIR}/../../../platform-py3-integration}
SOURCE_ROOT=$(CDPATH= cd -- "${SOURCE_INPUT}" && pwd -P)
BUILD_SOURCE_ROOT=${PY36_R1_ORA2_ASSET_BUILD_SOURCE:-/tmp/py36-p1b-ora2-asset-build-source-20260804-r25}
OUTPUT_ROOT=${PY36_R1_ORA2_BUILT_ASSET_ROOT:-/tmp/py36-p1b-ora2-assets-20260804-r29}
BUILDER_IMAGE=${PY36_R1_ORA2_ASSET_BUILDER_IMAGE:-ltdps/edxapp:py36-r1-p1b-ora2-asset-builder-20260804-r9}
NODE_MODULES_VOLUME=${PY36_R1_ORA2_NODE_MODULES_VOLUME:-devstack_edxapp_node_modules}
EXPECTED_COMMIT=7644241bb598ac20e20e70dd7abf2e5110f5b7bd
EXPECTED_TREE=7c5e963e767bb1eaa16c9e64222694698b7727a3
CONTAINER_SOURCE=/edx/app/edxapp/edx-platform
COMMON_PYTHONPATH=${CONTAINER_SOURCE}:${CONTAINER_SOURCE}/common/lib/xmodule:${CONTAINER_SOURCE}/common/lib/capa:${CONTAINER_SOURCE}/common/lib/dogstats:${CONTAINER_SOURCE}/common/lib/calc:${CONTAINER_SOURCE}/common/lib/chem:${CONTAINER_SOURCE}/common/lib/safe_lxml:${CONTAINER_SOURCE}/common/lib/sandbox-packages:${CONTAINER_SOURCE}/common/lib/symmath
CONTAINER_PATH=${CONTAINER_SOURCE}/node_modules/.bin:/usr/local/bin:/usr/bin:/bin

if [ "$(git -C "${SOURCE_ROOT}" rev-parse HEAD)" != "${EXPECTED_COMMIT}" ] || \
        [ "$(git -C "${SOURCE_ROOT}" rev-parse HEAD^{tree})" != "${EXPECTED_TREE}" ] || \
        [ -n "$(git -C "${SOURCE_ROOT}" status --porcelain=v1)" ]; then
    echo "refusing non-frozen or dirty asset source: ${SOURCE_ROOT}" >&2
    exit 2
fi
case "${BUILD_SOURCE_ROOT}" in
    /tmp/py36-p1b-ora2-asset-build-source-20260804-r[1-9]|/tmp/py36-p1b-ora2-asset-build-source-20260804-r[1-9][0-9]) ;;
    *) echo "refusing asset build source outside the gate root: ${BUILD_SOURCE_ROOT}" >&2; exit 2 ;;
esac
case "${OUTPUT_ROOT}" in
    /tmp/py36-p1b-ora2-assets-20260804-r[1-9]|/tmp/py36-p1b-ora2-assets-20260804-r[1-9][0-9]) ;;
    *) echo "refusing asset output outside the gate root: ${OUTPUT_ROOT}" >&2; exit 2 ;;
esac
if [ -e "${BUILD_SOURCE_ROOT}" ] || [ -e "${OUTPUT_ROOT}" ]; then
    echo "refusing to overwrite an asset build source or output" >&2
    exit 2
fi
docker image inspect "${BUILDER_IMAGE}" >/dev/null
docker volume inspect "${NODE_MODULES_VOLUME}" >/dev/null

git clone --quiet --no-hardlinks "${SOURCE_ROOT}" "${BUILD_SOURCE_ROOT}"
git -C "${BUILD_SOURCE_ROOT}" checkout --quiet --detach "${EXPECTED_COMMIT}"
if [ "$(git -C "${BUILD_SOURCE_ROOT}" rev-parse HEAD^{tree})" != "${EXPECTED_TREE}" ]; then
    echo "disposable asset source tree is invalid" >&2
    exit 1
fi
cp "${SCRIPT_DIR}/p1b_ora2_asset_lms_settings.py" "${BUILD_SOURCE_ROOT}/lms/envs/asset.py"
cp "${SCRIPT_DIR}/p1b_ora2_asset_cms_settings.py" "${BUILD_SOURCE_ROOT}/cms/envs/asset.py"
mkdir -p "${OUTPUT_ROOT}/assets" "${OUTPUT_ROOT}/logs"

BUILDER_IMAGE_ID=$(docker image inspect "${BUILDER_IMAGE}" --format '{{.Id}}')
docker run --rm \
    --mount "type=bind,src=${BUILD_SOURCE_ROOT},dst=${CONTAINER_SOURCE}" \
    --mount "type=volume,src=${NODE_MODULES_VOLUME},dst=${CONTAINER_SOURCE}/node_modules" \
    --env "PYTHONPATH=${COMMON_PYTHONPATH}" \
    --env "PATH=${CONTAINER_PATH}" \
    "${BUILDER_IMAGE}" sh -c \
    'python -c "import calc, capa, chem, dogstats_wrapper, openassessment, xmodule.static_content; print(openassessment.__file__)"; command -v webpack; command -v rtlcss; pip freeze | grep -i "^ora2 "' \
    >"${OUTPUT_ROOT}/logs/preflight.log" 2>&1
if ! rg -q '^ora2 @ git\+https://github.com/Learningtribes/edx-ora2@d3f24a9c539528e960c8dcc9aef200cea0c49baf$' \
        "${OUTPUT_ROOT}/logs/preflight.log"; then
    echo "asset builder does not contain the frozen ORA2 source" >&2
    exit 1
fi
BUILD_STARTED=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
BUILD_STARTED_EPOCH=$(date '+%s')
set +e
docker run --rm \
    --network devstack_default \
    --env NO_PREREQ_INSTALL=1 \
    --env "PYTHONPATH=${COMMON_PYTHONPATH}" \
    --env "PATH=${CONTAINER_PATH}" \
    --mount "type=bind,src=${BUILD_SOURCE_ROOT},dst=/edx/app/edxapp/edx-platform" \
    --mount "type=volume,src=${NODE_MODULES_VOLUME},dst=/edx/app/edxapp/edx-platform/node_modules" \
    --mount "type=bind,src=${OUTPUT_ROOT}/assets,dst=/edx/var/edxapp/staticfiles" \
    --workdir /edx/app/edxapp/edx-platform \
    "${BUILDER_IMAGE}" \
    sh -c 'python setup.py egg_info &&
        (cd common/lib/xmodule && python setup.py egg_info) &&
        (cd common/lib/capa && python setup.py egg_info) &&
        paver update_assets --settings=asset lms' \
    >"${OUTPUT_ROOT}/logs/paver-update-assets-lms.log" 2>&1
ASSET_STATUS=$?
set -e

JSI18N_STATUS=not-run
if [ "${ASSET_STATUS}" -eq 0 ]; then
    set +e
    docker run --rm \
        --network devstack_default \
        --env "PYTHONPATH=${COMMON_PYTHONPATH}" \
        --env "PATH=${CONTAINER_PATH}" \
        --mount "type=bind,src=${BUILD_SOURCE_ROOT},dst=/edx/app/edxapp/edx-platform" \
        --mount "type=volume,src=${NODE_MODULES_VOLUME},dst=/edx/app/edxapp/edx-platform/node_modules" \
        --mount "type=bind,src=${OUTPUT_ROOT}/assets,dst=/edx/var/edxapp/staticfiles" \
        --workdir /edx/app/edxapp/edx-platform \
        "${BUILDER_IMAGE}" \
        sh -c 'python manage.py lms --settings=asset compilejsi18n &&
            mkdir -p /edx/var/edxapp/staticfiles/js/i18n/en &&
            cp lms/static/js/i18n/en/djangojs.js /edx/var/edxapp/staticfiles/js/i18n/en/djangojs.js' \
        >"${OUTPUT_ROOT}/logs/compilejsi18n.log" 2>&1
    JSI18N_STATUS=$?
    set -e
fi

BUILD_FINISHED_EPOCH=$(date '+%s')
BUILD_DURATION=$((BUILD_FINISHED_EPOCH - BUILD_STARTED_EPOCH))
FINAL_STATUS=${ASSET_STATUS}
if [ "${JSI18N_STATUS}" != "0" ]; then
    FINAL_STATUS=1
fi
shasum -a 256 "${BUILD_SOURCE_ROOT}/lms/envs/asset.py" "${BUILD_SOURCE_ROOT}/cms/envs/asset.py" \
    >"${OUTPUT_ROOT}/logs/asset-settings.sha256"
printf '%s\n' \
    "source_commit=${EXPECTED_COMMIT}" \
    "source_tree=${EXPECTED_TREE}" \
    "source_copy=${BUILD_SOURCE_ROOT}" \
    "builder_image=${BUILDER_IMAGE}" \
    "builder_image_id=${BUILDER_IMAGE_ID}" \
    "node_modules_volume=${NODE_MODULES_VOLUME}" \
    "requested_command=uv run paver update_assets --system=lms" \
    "executed_command=python setup.py egg_info; xmodule/capa egg_info; paver update_assets --settings=asset lms" \
    "command_adjustment=Hawthorn Paver accepts positional systems; the builder has no uv" \
    "prereq_install=disabled; locked builder and node_modules inputs prevent development.txt source drift" \
    "build_started=${BUILD_STARTED}" \
    "build_duration_seconds=${BUILD_DURATION}" \
    "compilejsi18n_exit=${JSI18N_STATUS}" \
    "asset_build_exit=${FINAL_STATUS}" \
    >"${OUTPUT_ROOT}/logs/source-provenance.txt"

if [ "${FINAL_STATUS}" -ne 0 ]; then
    echo "ORA2 asset build failed: asset=${ASSET_STATUS} jsi18n=${JSI18N_STATUS}" >&2
    exit "${FINAL_STATUS}"
fi
printf 'ASSET_BUILD_OK root=%s source_commit=%s source_tree=%s duration=%s\n' \
    "${OUTPUT_ROOT}" "${EXPECTED_COMMIT}" "${EXPECTED_TREE}" "${BUILD_DURATION}"
