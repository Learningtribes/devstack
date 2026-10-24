"""Build the recorded real Hawthorn theme using pavelib.assets Sass lookup rules.

Run in the registered runtime with platform as cwd, before starting LMS/CMS.
The immutable /startup input is retained; only /runtime/themes is generated.
"""
import hashlib
import json
from pathlib import Path
import shutil

import sass

source = Path('/startup/theme-inputs/7c0dbec1b0a7/hawthorn')
record = json.loads((source.parent / 'source-sha256.json').read_text())
actual = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in source.rglob('*') if p.is_file()}
assert actual == record['files'], 'Theme input tree differs from registered commit'
print('Verified theme source:', record['commit'], len(actual), 'files', flush=True)
theme = Path('/runtime/themes-7c0dbec1b0a7/hawthorn')
shutil.copytree(source, theme, dirs_exist_ok=True)
common = ['common/static', 'common/static/sass', 'node_modules/@edx',
          'node_modules', 'node_modules/edx-pattern-library/node_modules']
outputs = {}
for system in ('lms', 'cms'):
    platform_sass = Path(system) / 'static/sass'
    theme_sass = theme / system / 'static/sass'
    dependencies = ['lms/static/sass/partials'] if system == 'cms' else []
    lookups = common + dependencies + [str(theme_sass / 'partials'),
                                      str(platform_sass / 'partials'), str(platform_sass)]
    count = 0
    for directory in (platform_sass, theme_sass):
        for entry in sorted(directory.rglob('*.scss')):
            if entry.name.startswith('_'):
                continue
            target = theme / system / 'static/css' / entry.relative_to(directory).with_suffix('.css')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(sass.compile(filename=str(entry), include_paths=lookups,
                                           output_style='expanded'))
            outputs[str(target.relative_to(theme))] = hashlib.sha256(target.read_bytes()).hexdigest()
            count += 1
    # DEBUG=False uses ThemeStorage's collected-static lookup. Stage the
    # compiled theme tree under the runtime static root so themed URLs resolve
    # after an HTTP process restart as well as in the build container.
    static_target = Path('/runtime/static') / system / 'hawthorn'
    shutil.copytree(theme / system / 'static', static_target, dirs_exist_ok=True)
    print(system, 'Sass entrypoints compiled:', count, flush=True)
(theme.parent / 'hawthorn-build-sha256.json').write_text(json.dumps(outputs, indent=2) + '\n')
print('Theme outputs:', len(outputs))
