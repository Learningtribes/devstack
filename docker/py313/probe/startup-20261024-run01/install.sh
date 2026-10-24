#!/bin/bash
set -euo pipefail
test -x /runtime/venv/bin/python || uv venv --python /usr/local/bin/python3.13 /runtime/venv
/usr/local/bin/python3.13 /startup/prepare_patched_sources.py
uv pip install --python /runtime/venv/bin/python --build-constraint /startup/build-constraints.txt --no-binary lxml --no-binary xmlsec --no-deps -r /startup/runtime-bootstrap.txt
for package in common/lib/calc common/lib/capa common/lib/chem common/lib/dogstats common/lib/safe_lxml common/lib/sandbox-packages common/lib/symmath common/lib/xmodule openedx/core/lib/xblock_builtin/xblock_discussion .; do
 uv pip install --python /runtime/venv/bin/python --no-deps -e "/edx/app/edxapp/edx-platform/$package"
done
uv pip check --python /runtime/venv/bin/python
