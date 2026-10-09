#!/bin/sh
# Re-run the image-dependent E3 gates (LMS/CMS check, import smoke) on the
# Markdown 2.6.11 rebuild. The Platform compile gate depends only on the source
# and the interpreter, both unchanged. Usage: e3-recheck.sh <out-dir>
set -u
OUT=$1
HERE=$(cd "$(dirname "$0")" && pwd)
E3=${HERE}/../e3
IMG=ltdps/edxapp:py36-r2-20261009
SRC=/Users/noahwang/workspace/hawthorn/platform-r2-py36-src
ID=$(docker image inspect "${IMG}" --format '{{.Id}}')
HEAD=$(git -C "${SRC}" rev-parse HEAD)
mkdir -p "${OUT}"

for svc in lms cms; do
    {
        echo "# image ${IMG} (${ID})"
        echo "# source ${HEAD} read-only; settings devstack_docker"
        "${E3}/r2-e3-run.sh" "${IMG}" "${SRC}" "${svc}" "md-${svc}-check" python \
            "manage.py ${svc} check --settings=devstack_docker 2>&1; echo \"${svc} check exit=\$?\""
    } > "${OUT}/${svc}-check.txt" 2>&1

    E3_EXTRA_MOUNT="type=bind,src=${E3}/import-smoke-files.txt,dst=/tmp/e3-smoke-files.txt,readonly" \
        "${E3}/r2-e3-run.sh" "${IMG}" "${SRC}" "${svc}" "md-${svc}-smoke" python \
        "manage.py ${svc} shell --settings=devstack_docker 2>&1" \
        < "${E3}/e3_import_smoke.py" > "${OUT}/import-smoke-${svc}.txt" 2>&1
done
