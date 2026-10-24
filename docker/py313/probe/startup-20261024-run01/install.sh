#!/bin/bash
set -euo pipefail
# LT ILT configures its real rotating file handler during plugin import.
install -d -m 700 /edx/var/log/lms /runtime/logs
test -x /runtime/venv/bin/python || uv venv --python /usr/local/bin/python3.13 /runtime/venv
/usr/local/bin/python3.13 /startup/prepare_patched_sources.py
uv pip install --python /runtime/venv/bin/python --build-constraint /startup/build-constraints.txt --no-binary lxml --no-binary xmlsec --no-deps -r /startup/runtime-bootstrap.txt
uv pip install --python /runtime/venv/bin/python 'setuptools==79.0.1'
if [[ "${PY313_PLATFORM_SOURCE_ROOT:-}" ]]; then
  source_root="$PY313_PLATFORM_SOURCE_ROOT"
  test -f "$source_root/manage.py"
  platform_root=/runtime/platform-source
  if [[ "$source_root" != "$platform_root" ]]; then
    test ! -e "$platform_root" || { echo "Writable platform copy already exists" >&2; exit 2; }
    cp -a "$source_root" "$platform_root"
  fi
  test -w "$platform_root/common/lib/calc"
  for package in common/lib/calc common/lib/capa common/lib/chem common/lib/dogstats common/lib/safe_lxml common/lib/sandbox-packages common/lib/symmath common/lib/xmodule openedx/core/lib/xblock_builtin/xblock_discussion .; do
    uv pip install --python /runtime/venv/bin/python --no-deps --editable "$platform_root/$package"
  done
else
  platform_root=/edx/app/edxapp/edx-platform
  for package in common/lib/calc common/lib/capa common/lib/chem common/lib/dogstats common/lib/safe_lxml common/lib/sandbox-packages common/lib/symmath common/lib/xmodule openedx/core/lib/xblock_builtin/xblock_discussion .; do
    uv pip install --python /runtime/venv/bin/python --no-deps -e "$platform_root/$package"
  done
fi
uv pip install --python /runtime/venv/bin/python --no-deps 'numpy>=1.24' 'scipy>=1.11' 'pyparsing>=3.0'
uv pip install --python /runtime/venv/bin/python --no-deps /runtime/rebuild-sources-20261025-run25/django-splash-1.3.0
uv pip install --python /runtime/venv/bin/python --no-deps /runtime/rebuild-sources-20261025-run25/django-require-1.0.11
uv pip install --python /runtime/venv/bin/python --no-deps /runtime/rebuild-sources-20261025-run25/jazkarta-edx-jsme-690dbf7
uv pip install --python /runtime/venv/bin/python --no-deps /runtime/rebuild-sources-20261025-run25/django-ratelimit-backend-2.0
uv pip install --python /runtime/venv/bin/python --no-deps /runtime/rebuild-sources-20261025-run25/edx_completion-5.0.0
uv pip install --python /runtime/venv/bin/python --no-deps /runtime/rebuild-sources-20261025-run25/djangosaml2idp-da3798e
uv pip install --python /runtime/venv/bin/python --no-deps /runtime/rebuild-sources-20261025-run25/pysaml2-7.5.5
uv pip install --python /runtime/venv/bin/python --no-deps /runtime/rebuild-sources-20261025-run25/edx-sga-0.28.0
uv pip install --python /runtime/venv/bin/python --no-deps /runtime/rebuild-sources-20261025-run25/edx-search-5.0.0-lt
uv pip check --python /runtime/venv/bin/python
