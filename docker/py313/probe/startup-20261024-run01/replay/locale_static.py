"""Build genuine locale/static products in the registered fresh runtime."""
from pathlib import Path
from django.core.management import call_command

path = Path('/startup/build_locale_assets.py')
exec(compile(path.read_text(), str(path), 'exec'))
call_command('collectstatic', interactive=False, verbosity=1)
