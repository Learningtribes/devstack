#!/bin/sh
# usage: run.sh PY(3.13|3.12) LAYER-NAME [extra uv args...]
set -e
PY=$1; L=$2; shift 2
cd "$(dirname "$0")"
python3 gen_inputs.py "${PLATFORM_DIR:-/Users/noahwang/workspace/hawthorn/platform-py313-spike}" "${UPSTREAM:-/Users/noahwang/docs/hawthorn/py313-upstream-verawood-base-2026-10-22.txt}" >/dev/null
OUT=resolved-$(echo $PY | tr -d .)-$L.txt
cp seed-verawood.txt $OUT
uv pip compile solver.in ${OVR:+--overrides overrides.txt} -c hard.txt --excludes excludes.txt --python-version $PY --python-platform aarch64-manylinux_2_36 --no-header "$@" -o $OUT 2>&1 | tail -${TAIL:-25}
