#!/bin/sh
set -eu

SOURCE_INPUT=${PLATFORM_INTEGRATION_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/../../../platform-py3-integration" && pwd -P)}
SOURCE_ROOT=$(CDPATH= cd -- "${SOURCE_INPUT}" && pwd -P)
INPUT_ROOT=${PY36_R1_ORA2_BUILT_ASSET_ROOT:-/tmp/py36-p1b-ora2-assets-20260804-r28}
STAGE_ROOT=${PY36_R1_ORA2_ASSET_STAGE_ROOT:-/tmp/py36-p1b-ora2-assessment-assets-20260804-r4}
PROTECTED_ROOT=/Users/noahwang/workspace/hawthorn/platform
EXPECTED_COMMIT=7644241bb598ac20e20e70dd7abf2e5110f5b7bd
EXPECTED_TREE=7c5e963e767bb1eaa16c9e64222694698b7727a3

if [ "${SOURCE_ROOT}" = "${PROTECTED_ROOT}" ]; then
    echo "refusing asset source: ${SOURCE_ROOT}" >&2
    exit 2
fi
if [ "$(git -C "${SOURCE_ROOT}" rev-parse HEAD)" != "${EXPECTED_COMMIT}" ] || \
        [ "$(git -C "${SOURCE_ROOT}" rev-parse HEAD^{tree})" != "${EXPECTED_TREE}" ] || \
        [ -n "$(git -C "${SOURCE_ROOT}" status --porcelain=v1)" ]; then
    echo "asset source is not the frozen ORA2 Platform commit/tree" >&2
    exit 2
fi
if [ ! -d "${INPUT_ROOT}/assets" ]; then
    echo "built asset root is missing assets/: ${INPUT_ROOT}" >&2
    exit 2
fi
if ! rg -q '^asset_build_exit=0$' "${INPUT_ROOT}/logs/source-provenance.txt" || \
        ! rg -q "^source_commit=${EXPECTED_COMMIT}$" "${INPUT_ROOT}/logs/source-provenance.txt" || \
        ! rg -q "^source_tree=${EXPECTED_TREE}$" "${INPUT_ROOT}/logs/source-provenance.txt"; then
    echo "built asset provenance is missing or invalid: ${INPUT_ROOT}" >&2
    exit 1
fi
case "${STAGE_ROOT}" in
    /tmp/py36-p1b-ora2-assessment-assets-20260804-r[1-9]|/tmp/py36-p1b-ora2-assessment-assets-20260804-r[1-9][0-9]) ;;
    *) echo "refusing asset stage outside the ORA2 gate root: ${STAGE_ROOT}" >&2; exit 2 ;;
esac
if [ -e "${STAGE_ROOT}" ]; then
    echo "refusing to overwrite asset stage: ${STAGE_ROOT}" >&2
    exit 2
fi

critical_assets='
bundles/Courseware.js
bundles/SequenceModule.js
css/lms-main-v1.css
js/i18n/en/djangojs.js
js/main.js
xblock/resources/openassessment.xblock/static/css/openassessment.css
xblock/resources/openassessment.xblock/static/js/openassessment-lms.min.js'
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

mkdir -p "${STAGE_ROOT}/py36/lms" "${STAGE_ROOT}/py27/lms" "${STAGE_ROOT}/build-logs"
cp -a "${INPUT_ROOT}/logs/." "${STAGE_ROOT}/build-logs/"
for runtime in py36 py27; do
    runtime_root="${STAGE_ROOT}/${runtime}/lms"
    cp -a "${INPUT_ROOT}/assets/." "${runtime_root}/"
    chmod -R a-w "${runtime_root}"
    file_count=$(find "${runtime_root}" -type f | wc -l | tr -d ' ')
    if [ "${file_count}" -lt 5000 ]; then
        echo "asset inventory is unexpectedly small for ${runtime}: ${file_count}" >&2
        exit 1
    fi
    for critical_asset in ${critical_assets}; do
        if [ ! -s "${runtime_root}/${critical_asset}" ]; then
            echo "staged asset is missing or empty for ${runtime}: ${critical_asset}" >&2
            exit 1
        fi
    done
    find "${runtime_root}" -type f -print | sort >"${STAGE_ROOT}/${runtime}-lms.inventory"
    find "${runtime_root}" -type f -exec shasum -a 256 {} \; | sort >"${STAGE_ROOT}/${runtime}-lms.sha256"
done

webpack_chunks=$(jq -r '.chunks | length' "${INPUT_ROOT}/assets/webpack-stats.json")
ora2_asset_hashes=$(find "${STAGE_ROOT}/py36/lms/xblock/resources/openassessment.xblock" -type f -exec shasum -a 256 {} \; | sort)
printf '%s\n' "${ora2_asset_hashes}" >"${STAGE_ROOT}/ora2-package-assets.sha256"
printf '%s\n' \
    "source_root=${SOURCE_ROOT}" \
    "source_commit=${EXPECTED_COMMIT}" \
    "source_tree=${EXPECTED_TREE}" \
    "input_root=${INPUT_ROOT}" \
    "stage_root=${STAGE_ROOT}" \
    "webpack_stats_status=done" \
    "webpack_stats_chunks=${webpack_chunks}" \
    "source_build_command_requested=uv run paver update_assets --system=lms" \
    "source_build_command_executed=paver update_assets --settings=asset lms" \
    "source_build_command_adjustment=Hawthorn Paver uses positional systems; the container has no uv" \
    "source_i18n_command_executed=python manage.py lms --settings=asset compilejsi18n" \
    >"${STAGE_ROOT}/asset-stage-ledger.txt"
printf 'ASSET_STAGE_OK root=%s source_commit=%s source_tree=%s\n' \
    "${STAGE_ROOT}" "${EXPECTED_COMMIT}" "${EXPECTED_TREE}"
