#!/bin/sh
set -eu

SOURCE_INPUT=${PLATFORM_INTEGRATION_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/../../../platform-py3-integration" && pwd -P)}
SOURCE_ROOT=$(CDPATH= cd -- "${SOURCE_INPUT}" && pwd -P)
INPUT_ROOT=${PY36_R1_STUDIO_BUILT_ASSET_ROOT:-/tmp/py36-p1b-studio-assets-r10}
STAGE_ROOT=${PY36_R1_STUDIO_ASSET_STAGE_ROOT:-/tmp/py36-p1b-studio-edit-publish-assets-20260803-r10}
PROTECTED_ROOT=/Users/noahwang/workspace/hawthorn/platform

if [ "$(basename -- "${SOURCE_ROOT}")" != "platform-py3-integration" ] || [ "${SOURCE_ROOT}" = "${PROTECTED_ROOT}" ]; then
    echo "refusing asset source: ${SOURCE_ROOT}" >&2
    exit 2
fi
if [ ! -d "${INPUT_ROOT}/assets" ]; then
    echo "built asset root is missing assets/: ${INPUT_ROOT}" >&2
    exit 2
fi
case "${STAGE_ROOT}" in
    /tmp/py36-p1b-studio-edit-publish-assets-20260803-r2|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r3|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r4|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r5|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r6|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r7|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r8|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r10|/tmp/py36-p1b-studio-edit-publish-assets-20260803-r11) ;;
    *) echo "refusing asset stage outside the gate root: ${STAGE_ROOT}" >&2; exit 2 ;;
esac
if [ -e "${STAGE_ROOT}" ]; then
    echo "refusing to overwrite asset stage: ${STAGE_ROOT}" >&2
    exit 2
fi

SOURCE_COMMIT=$(git -C "${SOURCE_ROOT}" rev-parse HEAD)
SOURCE_TREE=$(git -C "${SOURCE_ROOT}" rev-parse HEAD^{tree})
critical_assets='
bundles/CourseOutline.js
bundles/HtmlDescriptor.js
bundles/HtmlModule.js
bundles/LoginFactory.js
common/js/vendor/bootstrap.js
common/js/vendor/popper.js
js/i18n/en/djangojs.js
studio/images/studio-illustration.jpg'
for critical_asset in ${critical_assets}; do
    if [ ! -s "${INPUT_ROOT}/assets/${critical_asset}" ]; then
        echo "built asset is missing or empty: ${critical_asset}" >&2
        exit 1
    fi
done
if ! command -v jq >/dev/null 2>&1; then
    echo "jq is required to validate webpack stats" >&2
    exit 2
fi
if ! jq -e '(.status == "done") and ((.chunks | type) == "object") and ((.chunks | length) > 0)' \
        "${INPUT_ROOT}/assets/webpack-stats.json" >/dev/null; then
    echo "webpack stats are not a completed build: ${INPUT_ROOT}/assets/webpack-stats.json" >&2
    exit 1
fi
WEBPACK_STATS_CHUNKS=$(jq -r '.chunks | length' "${INPUT_ROOT}/assets/webpack-stats.json")
mkdir -p "${STAGE_ROOT}"/py36 "${STAGE_ROOT}"/py27

for runtime in py36 py27; do
    runtime_root="${STAGE_ROOT}/${runtime}"
    mkdir -p "${runtime_root}/lms" "${runtime_root}/studio"
    cp -a "${INPUT_ROOT}/assets/." "${runtime_root}/lms/"
    cp -a "${INPUT_ROOT}/assets/." "${runtime_root}/studio/"
    for asset_tree in lms studio; do
        if [ ! -s "${runtime_root}/${asset_tree}/studio/css/studio-main-v1.css" ]; then
            echo "built Studio CSS is missing for ${runtime}/${asset_tree}" >&2
            exit 1
        fi
        mkdir -p "${runtime_root}/${asset_tree}/css"
        cp -a "${runtime_root}/${asset_tree}/studio/css/." "${runtime_root}/${asset_tree}/css/"
    done
    chmod -R a-w "${runtime_root}/lms" "${runtime_root}/studio"
    lms_count=$(find "${runtime_root}/lms" -type f | wc -l | tr -d ' ')
    studio_count=$(find "${runtime_root}/studio" -type f | wc -l | tr -d ' ')
    if [ "${lms_count}" -lt 5000 ] || [ "${studio_count}" -lt 3000 ]; then
        echo "asset inventory is unexpectedly small for ${runtime}: lms=${lms_count} studio=${studio_count}" >&2
        exit 1
    fi
    if find "${runtime_root}" -type f \( -name '*.js' -o -name '*.css' -o -name '*.png' -o -name '*.jpg' -o -name '*.gif' -o -name '*.woff' -o -name '*.woff2' \) -size 0c | grep .; then
        echo "empty browser asset found for ${runtime}" >&2
        exit 1
    fi
    for critical_asset in ${critical_assets}; do
        if [ ! -s "${runtime_root}/lms/${critical_asset}" ] || [ ! -s "${runtime_root}/studio/${critical_asset}" ]; then
            echo "staged asset is missing or empty for ${runtime}: ${critical_asset}" >&2
            exit 1
        fi
    done
    for asset_tree in lms studio; do
        if [ ! -s "${runtime_root}/${asset_tree}/css/studio-main-v1.css" ]; then
            echo "staged Studio CSS compatibility path is missing for ${runtime}/${asset_tree}" >&2
            exit 1
        fi
    done
    find "${runtime_root}/lms" -type f -print | sort >"${STAGE_ROOT}/${runtime}-lms.inventory"
    find "${runtime_root}/studio" -type f -print | sort >"${STAGE_ROOT}/${runtime}-studio.inventory"
    find "${runtime_root}/lms" -type f -exec shasum -a 256 {} \; | sort >"${STAGE_ROOT}/${runtime}-lms.sha256"
    find "${runtime_root}/studio" -type f -exec shasum -a 256 {} \; | sort >"${STAGE_ROOT}/${runtime}-studio.sha256"
done

{
    printf '%s\n' "source_root=${SOURCE_ROOT}" "source_commit=${SOURCE_COMMIT}" "source_tree=${SOURCE_TREE}"
    printf '%s\n' "input_root=${INPUT_ROOT}" "stage_root=${STAGE_ROOT}"
    printf '%s\n' "webpack_stats_status=done" "webpack_stats_chunks=${WEBPACK_STATS_CHUNKS}"
    printf '%s\n' "source_build_command=paver update_assets lms studio --settings=devstack_docker --themes=no; manage.py lms/cms compilejsi18n; paver update_assets lms studio --settings=devstack_docker --themes=no"
    printf '%s\n' "source_build_command_requested=paver update_assets --system=lms,studio"
    printf '%s\n' "source_build_note=the comma-form command is unsupported by the installed Paver task; compatibility invocation was verified exit 0"
} >"${STAGE_ROOT}/asset-stage-ledger.txt"
printf 'ASSET_STAGE_OK root=%s source_commit=%s source_tree=%s\n' "${STAGE_ROOT}" "${SOURCE_COMMIT}" "${SOURCE_TREE}"
