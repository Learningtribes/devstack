"""Generate XModule inputs from registered classes, preserving prior outputs.

Execute through manage.py lms shell with full target settings before Sass/webpack.
An exclusive staging directory proves outputs do not depend on copied artifacts.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil

from django.conf import settings
from path import Path as LegacyPath
from xblock.core import XBlock
from xmodule import static_content

platform = Path(settings.PROJECT_ROOT)
staging = Path(os.environ.get('PY313_XMODULE_BUILD_ROOT', '/runtime/xmodule-source-build-v1'))
staging.mkdir(parents=True, exist_ok=False)
required = {'discussion', 'edx_sga', 'ilt', 'scormxblock', 'lti_consumer', 'html', 'problem', 'video'}
registered = dict(XBlock.load_classes())
assert required <= registered.keys(), sorted(required - registered.keys())
original_cwd = Path.cwd()
try:
    os.chdir(staging)
    root = LegacyPath('common/static/xmodule')
    descriptors = static_content.write_descriptor_js(root / 'descriptors/js')
    static_content.write_descriptor_styles(root / 'descriptors/css')
    modules = static_content.write_module_js(root / 'modules/js')
    static_content.write_module_styles(root / 'modules/css')
    static_content.write_webpack(root / 'webpack.xmodule.config.js', modules, descriptors)
finally:
    os.chdir(original_cwd)
generated = staging / 'common/static/xmodule'
manifest = {str(p.relative_to(generated)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(generated.rglob('*')) if p.is_file()}
assert descriptors and modules
for directory in ('descriptors/js', 'descriptors/css', 'modules/js', 'modules/css'):
    assert any(name.startswith(directory + '/') for name in manifest), directory
(staging / 'sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')
target = platform / 'common/static/xmodule'
backup = staging / 'preserved-prior-xmodule'
if target.exists():
    shutil.move(str(target), backup)
shutil.copytree(generated, target)
print(json.dumps({'generated_files': len(manifest), 'descriptors': len(descriptors),
                  'modules': len(modules), 'manifest': str(staging / 'sha256.json'),
                  'required_plugins': sorted(required), 'preserved_prior': str(backup)}, sort_keys=True))
