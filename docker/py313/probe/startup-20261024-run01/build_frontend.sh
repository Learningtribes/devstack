#!/bin/bash
# Run from the writable platform root after npm ci and build_xmodule_assets.py.
set -euo pipefail
export STATIC_ROOT_LMS=/runtime/static/lms
export STATIC_ROOT_CMS=/runtime/static/cms
mkdir -p "$STATIC_ROOT_LMS" "$STATIC_ROOT_CMS"
/runtime/venv/bin/python /startup/build_static_assets.py
/runtime/venv/bin/python /startup/build_theme_assets.py
./node_modules/.bin/webpack --config webpack.dev.config.js
/runtime/venv/bin/python - <<'PY'
import json
from pathlib import Path
for system in ('lms', 'cms'):
    stats = Path('/runtime/static') / system / 'webpack-stats.json'
    data = json.loads(stats.read_text())
    assert data['status'] == 'done', data['status']
    assert data['chunks']['LoginFactory']
    print(system, 'webpack stats ready:', len(data['chunks']), 'chunks')
PY
