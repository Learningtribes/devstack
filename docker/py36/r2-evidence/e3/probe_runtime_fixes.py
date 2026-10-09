# Run with: manage.py <lms|cms> shell --settings=devstack_docker < probe_runtime_fixes.py
from __future__ import print_function

import sys

from django.conf import settings
from django.db.migrations.loader import MigrationLoader

print('python', sys.version.split()[0])
print('proctoring_apps', [app for app in settings.INSTALLED_APPS if 'proctoring' in app])
print('migration_modules', settings.MIGRATION_MODULES)
print('heartbeat_es_timeout', getattr(settings, 'HEARTBEAT_ELASTICSEARCH_TIMEOUT', 'MISSING'))
loader = MigrationLoader(None, ignore_no_migrations=True)
print('submissions_migrations', sorted(
    (name, type(migration).__module__) for (app, name), migration in loader.disk_migrations.items()
    if app == 'submissions'
))
if settings.ROOT_URLCONF == 'lms.urls':
    from django.urls import get_resolver, reverse
    resolver = get_resolver()
    print('wiki_namespaces', sorted(ns for ns in resolver.namespace_dict if 'wiki' in ns))
    print('wiki_reverse', reverse('wiki:get', kwargs={'path': ''}))
    print('course_wiki_resolve', resolver.resolve('/courses/course-v1:a+b+c/wiki/').namespace)
