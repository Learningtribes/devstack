# -*- coding: utf-8 -*-
"""Isolation overlay for the disposable P1-B enrollment browser services."""
from __future__ import absolute_import, division, print_function, unicode_literals

import copy
import os

from lms.envs.devstack_docker import *  # noqa: F401,F403
from xmodule.modulestore.modulestore_settings import update_module_store_settings


BROWSER_NAMESPACE = os.environ.get('PY36_R1_BROWSER_NAMESPACE')
if not BROWSER_NAMESPACE:
    raise RuntimeError('PY36_R1_BROWSER_NAMESPACE is required')

COLLECTED_STATIC_ROOT = STATIC_ROOT
STATIC_ROOT = os.path.join('/tmp', BROWSER_NAMESPACE, 'staticfiles-output')
STATICFILES_DIRS = [COLLECTED_STATIC_ROOT] + list(STATICFILES_DIRS)

INSTALLED_APPS = list(INSTALLED_APPS)
if not any(app.startswith('edx_proctoring') for app in INSTALLED_APPS):
    INSTALLED_APPS.append('edx_proctoring.apps.EdxProctoringConfig')
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'debug_toolbar']

MIDDLEWARE_CLASSES = [
    middleware for middleware in MIDDLEWARE_CLASSES
    if middleware not in (
        'django_comment_client.utils.QueryCountDebugMiddleware',
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    )
]

FEATURES = copy.deepcopy(FEATURES)
FEATURES.update({
    'ALLOW_PUBLIC_ACCOUNT_CREATION': True,
    'ENABLE_DISCUSSION_SERVICE': False,
    'RESTRICT_AUTOMATIC_AUTH': False,
})

COURSE_REVIEWS_TOOL_PROVIDER_FRAGMENT_NAME = None
COURSE_REVIEWS_TOOL_PROVIDER_PLATFORM_KEY = None

CACHES = {
    alias: {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': '{}:{}'.format(BROWSER_NAMESPACE, alias),
    }
    for alias in CACHES
}

DATABASES = copy.deepcopy(DATABASES)
for database in DATABASES.values():
    database['CONN_MAX_AGE'] = 0

DOC_STORE_CONFIG = copy.deepcopy(DOC_STORE_CONFIG)
DOC_STORE_CONFIG.update({
    'db': '{}_edxapp'.format(BROWSER_NAMESPACE),
    'user': None,
    'password': None,
})
MODULESTORE = copy.deepcopy(MODULESTORE)
update_module_store_settings(
    MODULESTORE,
    doc_store_settings=DOC_STORE_CONFIG,
    module_store_options={'fs_root': '/edx/var/edxapp/data'},
)

CONTENTSTORE = copy.deepcopy(CONTENTSTORE)
if CONTENTSTORE:
    CONTENTSTORE.setdefault('DOC_STORE_CONFIG', {}).update({
        'db': '{}_xcontent'.format(BROWSER_NAMESPACE),
        'user': None,
        'password': None,
    })
