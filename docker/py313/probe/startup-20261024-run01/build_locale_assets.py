"""Compile real platform catalogs and every configured static JS locale.

Run through each system's manage.py shell after configuring /runtime/locale
in LOCALE_PATHS. Sources remain untouched; outputs live on the runtime volume.
"""
import hashlib
import json
from pathlib import Path
import subprocess

from django.conf import settings
from django.core.management import call_command
from django.utils import translation

root = Path(settings.PROJECT_ROOT)
source = root / 'conf/locale'
destination = Path('/runtime/locale')
manifest = {}
catalogs_on_disk = sorted(source.glob('*/LC_MESSAGES/*.po'))
if (root / '.git').exists():
    # A live-mounted checkout carries ignored leftovers (*.po is gitignored, e.g. django-saved.po) that
    # the committed export never contains; compile only what Platform tracks.
    tracked = set(subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z', '--', 'conf/locale'],
                                          text=True).split('\0'))
    catalogs_on_disk = [po for po in catalogs_on_disk if str(po.relative_to(root)) in tracked]
for po in catalogs_on_disk:
    relative = po.relative_to(source)
    mo = (destination / relative).with_suffix('.mo')
    mo.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['msgfmt', '--check', '-o', str(mo), str(po)], check=True)
    manifest[str(relative)] = hashlib.sha256(po.read_bytes()).hexdigest()

# Catalogs must be loaded after the compiled files exist in this process.
translation.trans_real._translations.clear()
output = Path(settings.STATIC_ROOT) / 'js/i18n'
call_command('compilejsi18n', outputdir=str(output))
catalogs = sorted(output.glob('*/djangojs.js'))
assert (output / 'zh-cn/djangojs.js').is_file()
assert len(catalogs) >= len(settings.LANGUAGES)
manifest['outputs'] = {
    str(item.relative_to(output)): hashlib.sha256(item.read_bytes()).hexdigest()
    for item in catalogs
}
(output / 'build-sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Compiled', len(manifest) - 1, 'PO sources and', len(catalogs), 'JS catalogs')
