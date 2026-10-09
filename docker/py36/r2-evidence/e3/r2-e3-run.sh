#!/bin/sh
# usage: r2-e3-run.sh <image> <src> <svc> <label> <python> <command...>
IMG=$1; SRC=$2; SVC=$3; LABEL=$4; shift 4
C=/Users/noahwang/workspace/hawthorn/.py36-r2-config
P=/edx/app/edxapp/edx-platform
L=$P/common/lib
exec docker run --rm -i --name "py36-r2-e3-$LABEL" --label io.openedx.py36-r2.gate=e3-check \
  --network devstack_default \
  --mount "type=bind,src=$SRC,dst=$P,readonly" \
  --mount "type=bind,src=/Users/noahwang/workspace/hawthorn/src,dst=/edx/src,readonly" \
  --mount "type=bind,src=$C/$SVC.auth.json,dst=/edx/app/edxapp/$SVC.auth.json,readonly" \
  --mount "type=bind,src=$C/$SVC.env.json,dst=/edx/app/edxapp/$SVC.env.json,readonly" \
  --mount type=tmpfs,dst=/edx/var/log \
  --mount type=tmpfs,dst=/tmp/e3work \
  ${E3_EXTRA_MOUNT:+--mount "$E3_EXTRA_MOUNT"} \
  -w $P \
  -e SERVICE_VARIANT=$SVC -e PYTHONDONTWRITEBYTECODE=1 \
  -e PYTHONPATH=/edx/app/edxapp:$P:$L/xmodule:$L/capa:$L/calc:$L/safe_lxml:$L/symmath:$L/chem:$L/dogstats \
  -e EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo -e NO_PYTHON_UNINSTALL=1 \
  --entrypoint sh "$IMG" -c "$*"
