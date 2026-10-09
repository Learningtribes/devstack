# Run with: manage.py <lms|cms> shell --settings=devstack_docker < e3_import_smoke.py
# Reads repo-relative paths from /tmp/e3-smoke-files.txt and imports the
# ones owned by the current service under their sys.path module names.
from __future__ import print_function

import importlib
import sys
import traceback

from django.conf import settings

SERVICE = 'cms' if settings.ROOT_URLCONF == 'cms.urls' else 'lms'
TOP_LEVEL_ROOTS = ('lms/djangoapps/', 'cms/djangoapps/', 'common/djangoapps/')


import os

from django.apps import apps

REPO = os.getcwd()
APP_ROOTS = []
for config in apps.get_app_configs():
    if os.path.realpath(config.path).startswith(REPO + '/'):
        APP_ROOTS.append((os.path.relpath(config.path, REPO) + '/', config.name))
APP_ROOTS.sort(key=lambda item: len(item[0]), reverse=True)


# `manage.py shell` execs stdin inside a function, so module-level names are not
# visible from nested functions; bind them as defaults. Installed apps are
# imported under their INSTALLED_APPS name to avoid double model registration.
def module_name(path, top_level_roots=TOP_LEVEL_ROOTS, app_roots=APP_ROOTS):
    path = path[:-len('.py')]
    if path.endswith('/__init__'):
        path = path[:-len('/__init__')]
    for root, app_name in app_roots:
        if (path + '/').startswith(root):
            rest = path[len(root):].replace('/', '.')
            return app_name + ('.' + rest if rest else '')
    for root in top_level_roots:
        if path.startswith(root):
            return path[len(root):].replace('/', '.')
    if path.startswith('common/lib/'):
        return path.split('/', 3)[3].replace('/', '.')
    return path.replace('/', '.')


def owner(path):
    return 'cms' if path.startswith('cms/') else 'lms'


with open('/tmp/e3-smoke-files.txt') as listing:
    paths = [line.strip() for line in listing if line.strip()]

ok, failed = [], []
for path in paths:
    if owner(path) != SERVICE:
        continue
    name = module_name(path)
    try:
        importlib.import_module(name)
    except Exception:  # pylint: disable=broad-except
        failed.append((path, name, traceback.format_exc().strip().splitlines()[-1]))
    else:
        ok.append(name)

print('python', sys.version.split()[0], 'service', SERVICE)
print('imported_ok', len(ok))
print('import_failed', len(failed))
for path, name, error in failed:
    print('  FAIL', path, name, error)
