#!/bin/sh
# R2-preview E6 static assets from the frozen R2 source.
# usage: r2-build-e6-assets.sh {compile|collect} [out-root]
#
# compile: one Python 2.7 runner pass (node, Paver, Platform-pinned libsass)
#          over a disposable clone: jsi18n, XModule/npm assets, webpack, Sass.
# collect: collectstatic per runtime with that runtime's own image, so
#          xblock/resources/ comes from the XBlock packages it has installed.
# Each runtime tree is mounted read-only at /edx/var/edxapp/staticfiles for
# both LMS and Studio (Studio's STATIC_ROOT is its studio/ subdirectory).
# Every container runs with --network none; the shared node_modules volume is
# mounted read-only after its lockfile is proven equal to the R2 source.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
WORKSPACE=/Users/noahwang/workspace/hawthorn
SOURCE_ROOT=${WORKSPACE}/platform-r2-py36-src
EXPECTED_COMMIT=0ac3bfa6d099916cc58fc258db17221801f49d48
CONFIG=${WORKSPACE}/.py36-r2-config
XBLOCK_ILT_COMMIT=52b0f1cb1f49858a6bfd9a4663c09eec73c5918c
XBLOCK_ILT_SRC=${WORKSPACE}/.py36-r2-sources/xblock-ilt-${XBLOCK_ILT_COMMIT}
NODE_MODULES_VOLUME=devstack_edxapp_node_modules
PY36_IMAGE=ltdps/edxapp:py36-r2-20261009
PY27_IMAGE=ltdps/edxapp:py36-r2-py27-runner-20261009
PY27_IMAGE_ID=sha256:e5ecccf98eb9b9f9d7cb04d7f04a08d62cf29ce19a7e8f3c2230e5cf67396b89
ACTION=${1:-}
OUT=${2:-/tmp/py36-r2-e6-assets-20261010-r1}
LABEL=io.openedx.py36-r2.gate=e6-assets
P=/edx/app/edxapp/edx-platform
L=${P}/common/lib
STATIC=/edx/var/edxapp/staticfiles
PY27=/edx/app/edxapp/venvs/edxapp/bin/python
PYTHONPATH_VALUE=/runner/source-metadata:${P}:${L}/xmodule:${L}/capa:${P}/openedx/core/lib/xblock_builtin/xblock_discussion:${L}/calc:${L}/safe_lxml:${L}/symmath:${L}/chem:${L}/dogstats
PY27_METADATA="${PY27} /opt/runner/py27_source_metadata.py /runner/source-metadata ${P}/setup.py ${L}/xmodule/setup.py ${L}/capa/setup.py ${P}/openedx/core/lib/xblock_builtin/xblock_discussion/setup.py >/dev/null"
# ilt-xblock opens a file handler at /edx/var/log/lms/ilt_xblock.log on import.
LOG_DIRS='mkdir -p /edx/var/log/lms /edx/var/log/cms'
# pavelib.assets.collect_assets
COLLECT_ARGS="--ignore fixtures --ignore 'karma_*.js' --ignore spec --ignore spec_helpers --ignore spec-helpers --ignore xmodule_js --ignore geoip --ignore sass --noinput"

case "${OUT}" in
    /tmp/py36-r2-e6-assets-20261010-r[1-9]) ;;
    *) echo "refusing asset root outside the gate root: ${OUT}" >&2; exit 2 ;;
esac
test "$(git -C "${SOURCE_ROOT}" rev-parse HEAD)" = "${EXPECTED_COMMIT}"
test -z "$(git -C "${SOURCE_ROOT}" status --porcelain)"
test "$(docker image inspect "${PY27_IMAGE}" --format '{{.Id}}')" = "${PY27_IMAGE_ID}"
grep -qx "commit=${XBLOCK_ILT_COMMIT}" "${XBLOCK_ILT_SRC}.identity"

common_args() {
    printf '%s\n' \
        --rm --network none --label "${LABEL}" --entrypoint /bin/sh --memory "${PY36_R2_GATE_ASSET_MEMORY:-6g}" \
        --mount "type=bind,src=${WORKSPACE}/src,dst=/edx/src,readonly" \
        --mount "type=bind,src=${XBLOCK_ILT_SRC},dst=/edx/src/xblock-ilt,readonly" \
        --mount "type=bind,src=${CONFIG}/lms.auth.json,dst=/edx/app/edxapp/lms.auth.json,readonly" \
        --mount "type=bind,src=${CONFIG}/lms.env.json,dst=/edx/app/edxapp/lms.env.json,readonly" \
        --mount "type=bind,src=${CONFIG}/cms.auth.json,dst=/edx/app/edxapp/cms.auth.json,readonly" \
        --mount "type=bind,src=${CONFIG}/cms.env.json,dst=/edx/app/edxapp/cms.env.json,readonly" \
        --mount type=tmpfs,dst=/runner \
        --mount type=tmpfs,dst=/edx/var/log \
        --env "PYTHONPATH=${PYTHONPATH_VALUE}" --env PYTHONDONTWRITEBYTECODE=1 \
        --env NO_PREREQ_INSTALL=1 --env NO_PYTHON_UNINSTALL=1 \
        -w "${P}"
}

compile() {
    if [ -e "${OUT}" ]; then echo "refusing to overwrite ${OUT}" >&2; exit 2; fi
    mkdir -p "${OUT}/logs" "${OUT}/compile"
    git clone --quiet --no-hardlinks "${SOURCE_ROOT}" "${OUT}/source"
    git -C "${OUT}/source" checkout --quiet --detach "${EXPECTED_COMMIT}"
    cp "${SCRIPT_DIR}/r2_e6_asset_settings.py" "${OUT}/source/lms/envs/r2_e6_asset.py"
    cp "${SCRIPT_DIR}/r2_e6_asset_settings.py" "${OUT}/source/cms/envs/r2_e6_asset.py"
    # compile_sass writes each theme's CSS into the theme directory itself, and
    # the shared src/themes (COMPREHENSIVE_THEME_DIRS) is not a git checkout.
    cp -a "${WORKSPACE}/src/themes" "${OUT}/themes"
    (cd "${OUT}/themes" && echo "themes_input_files=$(find . -type f | wc -l | tr -d ' ') sha256=$(find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1)") \
        > "${OUT}/logs/themes-input.txt"

    docker run --rm --network none --mount "type=volume,src=${NODE_MODULES_VOLUME},dst=/nm,readonly" busybox \
        cat /nm/.package-lock.json > "${OUT}/logs/node-modules-hidden-lock.json"
    jq -S '.packages | del(.[""]) | map_values(.version)' "${OUT}/logs/node-modules-hidden-lock.json" > "${OUT}/logs/node-modules.versions.json"
    jq -S '.packages | del(.[""]) | map_values(.version)' "${OUT}/source/package-lock.json" > "${OUT}/logs/package-lock.versions.json"
    if ! cmp -s "${OUT}/logs/node-modules.versions.json" "${OUT}/logs/package-lock.versions.json"; then
        echo "node_modules volume does not match the R2 package-lock.json" >&2
        exit 1
    fi

    started=$(date '+%s')
    # shellcheck disable=SC2046
    docker run $(common_args) --platform linux/amd64 \
        --mount "type=bind,src=${OUT}/source,dst=${P}" \
        --mount "type=volume,src=${NODE_MODULES_VOLUME},dst=${P}/node_modules,readonly" \
        --mount "type=tmpfs,dst=${P}/node_modules/.cache" \
        --mount "type=bind,src=${OUT}/compile,dst=${STATIC}" \
        --mount "type=bind,src=${OUT}/themes,dst=/edx/src/themes" \
        --env "PATH=/edx/app/edxapp/venvs/edxapp/bin:/edx/app/edxapp/nodeenvs/edxapp/bin:${P}/node_modules/.bin:/usr/local/bin:/usr/bin:/bin" \
        "${PY27_IMAGE}" -c "${LOG_DIRS} && ${PY27_METADATA} &&
            python manage.py lms --settings=r2_e6_asset compilejsi18n &&
            python manage.py cms --settings=r2_e6_asset compilejsi18n &&
            paver update_assets lms studio --settings=r2_e6_asset --skip-collect" \
        > "${OUT}/logs/compile.log" 2>&1
    echo "compile_seconds=$(($(date '+%s') - started))" > "${OUT}/logs/compile-seconds.txt"
    for stats in webpack-stats.json studio/webpack-stats.json; do
        jq -e '(.status == "done") and ((.chunks | length) > 0)' "${OUT}/compile/${stats}" >/dev/null
    done
    echo "E6_ASSETS_COMPILED root=${OUT}"
}

collect_runtime() {
    runtime=$1; image=$2; platform=$3; python=$4; prefix=$5
    mkdir -p "${OUT}/${runtime}"
    # shellcheck disable=SC2046
    # update_assets leaves common/static/edx-{ui-toolkit,pattern-library} as
    # symlinks into node_modules, so collectstatic needs the same volume.
    docker run $(common_args) --platform "${platform}" \
        --mount "type=bind,src=${OUT}/source,dst=${P},readonly" \
        --mount "type=volume,src=${NODE_MODULES_VOLUME},dst=${P}/node_modules,readonly" \
        --mount "type=bind,src=${OUT}/${runtime},dst=${STATIC}" \
        --mount "type=bind,src=${OUT}/themes,dst=/edx/src/themes,readonly" \
        "${image}" -c "${LOG_DIRS} && ${prefix}${python} manage.py lms --settings=r2_e6_asset collectstatic ${COLLECT_ARGS} &&
            ${python} manage.py cms --settings=r2_e6_asset collectstatic ${COLLECT_ARGS}" \
        > "${OUT}/logs/collect-${runtime}.log" 2>&1
    cp "${OUT}/compile/webpack-stats.json" "${OUT}/${runtime}/webpack-stats.json"
    cp "${OUT}/compile/studio/webpack-stats.json" "${OUT}/${runtime}/studio/webpack-stats.json"
}

collect() {
    py36_image_id=${PY36_R2_IMAGE_ID:?set PY36_R2_IMAGE_ID to the expected Python 3.6 image ID}
    test "$(docker image inspect "${PY36_IMAGE}" --format '{{.Id}}')" = "${py36_image_id}"
    test -f "${OUT}/logs/compile-seconds.txt"
    docker run --rm --network none --mount "type=volume,src=${NODE_MODULES_VOLUME},dst=/nm,readonly" busybox \
        cat /nm/.package-lock.json | cmp -s - "${OUT}/logs/node-modules-hidden-lock.json" ||
        { echo "node_modules volume changed since compile" >&2; exit 1; }
    for runtime in py27 py36; do
        if [ -e "${OUT}/${runtime}" ]; then echo "refusing to overwrite ${OUT}/${runtime}" >&2; exit 2; fi
    done
    started=$(date '+%s')
    collect_runtime py27 "${PY27_IMAGE}" linux/amd64 "${PY27}" "${PY27_METADATA} && "
    collect_runtime py36 "${PY36_IMAGE}" linux/arm64 python ''
    collect_seconds=$(($(date '+%s') - started))

    critical='
bundles/IltGlobals.js
bundles/Courseware.js
css/lms-main-v1.css
js/main.js
js/i18n/en/djangojs.js
studio/bundles/LoginFactory.js
studio/bundles/CourseOutline.js
studio/css/studio-main-v1.css
studio/js/i18n/en/djangojs.js'
    for runtime in py27 py36; do
        for asset in ${critical}; do
            test -s "${OUT}/${runtime}/${asset}" || { echo "missing or empty ${runtime}/${asset}" >&2; exit 1; }
        done
        if grep -q FeedbackForm "${OUT}/${runtime}/js/main.js"; then
            echo "${runtime}/js/main.js is not the R2 source" >&2
            exit 1
        fi
        (cd "${OUT}/${runtime}" && find . -type f | LC_ALL=C sort > "${OUT}/logs/${runtime}.inventory" &&
            find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 > "${OUT}/logs/${runtime}.sha256")
        chmod -R a-w "${OUT}/${runtime}"
    done
    # App static dirs come from each runtime's installed packages and may
    # differ; everything the shared compile step produced must not.
    diff "${OUT}/logs/py27.sha256" "${OUT}/logs/py36.sha256" > "${OUT}/logs/py27-vs-py36.diff" || true
    grep -E '^[<>]' "${OUT}/logs/py27-vs-py36.diff" |
        awk '{n = split($3, p, "/"); d = (n > 3) ? p[2] "/" p[3] : p[2]; c[$1 " " d]++} END {for (k in c) print c[k], k}' |
        LC_ALL=C sort -k3 -k2 > "${OUT}/logs/py27-vs-py36.by-dir.txt"
    compiled='^[<>] [0-9a-f]{64}  \./(studio/)?(bundles|js/i18n|hawthorn)/|^[<>] [0-9a-f]{64}  \./(css/lms-|studio/css/studio-)'
    if grep -E "${compiled}" "${OUT}/logs/py27-vs-py36.diff" > "${OUT}/logs/py27-vs-py36.compiled.diff"; then
        echo "compiled assets differ between runtimes" >&2
        exit 1
    fi

    {
        echo "source_root=${SOURCE_ROOT}"
        echo "source_commit=${EXPECTED_COMMIT}"
        echo "source_tree=$(git -C "${OUT}/source" rev-parse HEAD^{tree})"
        echo "devstack_commit=$(git -C "${SCRIPT_DIR}" rev-parse HEAD)"
        echo "compile_image=${PY27_IMAGE} ${PY27_IMAGE_ID}"
        echo "collect_py27_image=${PY27_IMAGE} ${PY27_IMAGE_ID}"
        echo "collect_py36_image=${PY36_IMAGE} ${py36_image_id}"
        echo "source_untracked=lms/envs/r2_e6_asset.py cms/envs/r2_e6_asset.py = r2_e6_asset_settings.py sha256 $(shasum -a 256 "${SCRIPT_DIR}/r2_e6_asset_settings.py" | cut -d' ' -f1)"
        echo "source_status=$(git -C "${OUT}/source" status --porcelain --untracked-files=no | wc -l | tr -d ' ') tracked changes"
        echo "xblock_ilt=${XBLOCK_ILT_COMMIT}"
        echo "node_modules_volume=${NODE_MODULES_VOLUME} (read-only; versions equal to package-lock.json, $(jq length "${OUT}/logs/package-lock.versions.json") packages)"
        echo "compile_command=compilejsi18n lms+cms; paver update_assets lms studio --settings=r2_e6_asset --skip-collect"
        echo "collect_command=manage.py {lms,cms} --settings=r2_e6_asset collectstatic ${COLLECT_ARGS}"
        echo "themes=copy of ${WORKSPACE}/src/themes (not a git checkout), compiled in the copy; $(cat "${OUT}/logs/themes-input.txt")"
        cat "${OUT}/logs/compile-seconds.txt"
        echo "collect_seconds=${collect_seconds}"
        for runtime in py27 py36; do
            echo "${runtime}_files=$(wc -l < "${OUT}/logs/${runtime}.inventory" | tr -d ' ')"
        done
        echo "py27_vs_py36_changed_lines=$(grep -c -E '^[<>]' "${OUT}/logs/py27-vs-py36.diff" || true)"
        echo "py27_only_or_changed=$(grep -c '^<' "${OUT}/logs/py27-vs-py36.diff" || true) py36_only_or_changed=$(grep -c '^>' "${OUT}/logs/py27-vs-py36.diff" || true) compiled_differences=0 (by dir: py27-vs-py36.by-dir.txt)"
    } > "${OUT}/logs/provenance.txt"
    cat "${OUT}/logs/provenance.txt"
    echo "E6_ASSETS_OK root=${OUT}"
}

case "${ACTION}" in
    compile) compile ;;
    collect) collect ;;
    *) echo "usage: $0 {compile|collect} [out-root]" >&2; exit 2 ;;
esac
