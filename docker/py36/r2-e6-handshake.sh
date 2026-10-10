#!/bin/sh
# Stand-in for an R1 service script inside the E6 browser container, which has
# no Docker: `handshake.sh <runtime> <action>` files a request under
# /work/out/handshake and prints the answer the gate wrapper writes on the host
# (<id>.out, then <id>.rc), exiting with its status.
set -eu
dir=/work/out/handshake
id="$2-${PY36_R1_STUDIO_ATTEMPT:-0}"
mkdir -p "${dir}"
rm -f "${dir}/${id}.out" "${dir}/${id}.rc"
printf '%s %s %s\n' "$1" "$2" "${PY36_R1_STUDIO_ATTEMPT:-0}" > "${dir}/${id}.request.tmp"
mv "${dir}/${id}.request.tmp" "${dir}/${id}.request"
tries=0
until [ -f "${dir}/${id}.rc" ]; do
    tries=$((tries + 1))
    if [ "${tries}" -ge 1150 ]; then echo "handshake timeout: ${id}" >&2; exit 124; fi
    sleep 0.1
done
cat "${dir}/${id}.out"
exit "$(cat "${dir}/${id}.rc")"
