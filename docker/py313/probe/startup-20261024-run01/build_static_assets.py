"""Build legacy vendor/Sass assets without importing unrelated paver test tasks.

Inputs mirror pavelib.assets manifests and Open edX default (un-themed) paths.
Run in the disposable writable source build container; no databases involved.
"""
import ast
from pathlib import Path
import shutil
import sass

source = ast.parse(Path('pavelib/assets.py').read_text())
manifest = next(ast.literal_eval(n.value) for n in source.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'NPM_INSTALLED_LIBRARIES' for t in n.targets))
for name in manifest:
    src = Path('node_modules') / name
    if not src.exists():
        raise FileNotFoundError(src)
    target = Path('common/static/common/css/vendor' if name.endswith(('.css', '.css.map')) else 'common/static/common/js/vendor') / name.rstrip('/').split('/')[-1]
    target.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        # Preserve package directory, matching GNU cp -rfT in pavelib.assets.
        target = Path('common/static/common/js/vendor') / name.rstrip('/')
        shutil.copytree(src, target, dirs_exist_ok=True)
    else:
        shutil.copy2(src, target)
print('Vendor manifest copied:', len(manifest))
common = ['common/static', 'common/static/sass', 'node_modules/@edx', 'node_modules', 'node_modules/edx-pattern-library/node_modules']
failures = []
for system, directory in [('common', 'common/static'), ('lms', 'lms/static'), ('cms', 'cms/static'), ('lms', 'lms/static/certificates')]:
    prefix = Path(directory)
    lookups = common + ([str(Path(system)/'static/sass/partials'), str(Path(system)/'static/sass')] if system != 'common' else [])
    if system == 'cms':
        lookups += ['lms/static/sass/partials']
    for entry in sorted((prefix/'sass').rglob('*.scss')):
        if entry.name.startswith('_'):
            continue
        print('Compiling:', entry, flush=True)
        target = prefix/'css'/entry.relative_to(prefix/'sass').with_suffix('.css')
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(sass.compile(filename=str(entry), include_paths=lookups, output_style='expanded'))
        except sass.CompileError as exc:
            failures.append(str(entry))
            print('FAILED:', entry, str(exc), flush=True)
    print('Sass compiled:', directory)

if failures:
    raise SystemExit("Sass compilation failed: " + ", ".join(failures))
