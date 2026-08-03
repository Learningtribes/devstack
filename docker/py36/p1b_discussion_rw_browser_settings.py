# -*- coding: utf-8 -*-
"""Runtime overlay for the isolated P1-B discussion read/write gate."""
from __future__ import absolute_import, division, print_function, unicode_literals

import copy
import os
from six.moves.urllib.parse import urlparse

from lms.envs.devstack_docker import *  # noqa: F401,F403
from xmodule.modulestore.modulestore_settings import update_module_store_settings


DISCUSSION_RUNTIME = os.environ.get('PY36_R1_DISCUSSION_RUNTIME')
DISCUSSION_NAMESPACE = os.environ.get('PY36_R1_DISCUSSION_NAMESPACE')
if not DISCUSSION_RUNTIME or not DISCUSSION_NAMESPACE:
    raise RuntimeError('discussion runtime and namespace are required')


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError('{} is required'.format(name))
    return value


COMMENTS_SERVICE_URL = _required('COMMENTS_SERVICE_URL')
COMMENTS_SERVICE_KEY = _required('COMMENTS_SERVICE_KEY')
SITE_NAME = _required('PY36_R1_DISCUSSION_SITE_DOMAIN')
LMS_BASE = SITE_NAME
LMS_ROOT_URL = 'http://{}'.format(SITE_NAME)
LMS_INTERNAL_ROOT_URL = LMS_ROOT_URL
DISCUSSION_SQL_DATABASE = _required('PY36_R1_DISCUSSION_SQL_DATABASE')
DISCUSSION_SQL_HISTORY_DATABASE = os.environ.get(
    'PY36_R1_DISCUSSION_SQL_HISTORY_DATABASE',
    DISCUSSION_SQL_DATABASE,
)
DISCUSSION_SQL_USER = _required('PY36_R1_DISCUSSION_SQL_USER')
DISCUSSION_SQL_PASSWORD = _required('PY36_R1_DISCUSSION_SQL_PASSWORD')
DISCUSSION_SEARCH_SERVER = _required('PY36_R1_DISCUSSION_SEARCH_SERVER').rstrip('/')

COLLECTED_STATIC_ROOT = STATIC_ROOT
STATIC_ROOT = os.path.join('/tmp', DISCUSSION_NAMESPACE, 'staticfiles-output')
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
    'ALLOW_AUTOMATED_SIGNUPS': True,
    'ALLOW_PUBLIC_ACCOUNT_CREATION': True,
    'AUTOMATIC_AUTH_FOR_TESTING': True,
    'ENABLE_DISCUSSION_SERVICE': True,
    'ENABLE_LAST_ACTIVITY': True,
    'RESTRICT_AUTOMATIC_AUTH': False,
})

COURSE_REVIEWS_TOOL_PROVIDER_FRAGMENT_NAME = None
COURSE_REVIEWS_TOOL_PROVIDER_PLATFORM_KEY = None

# This is consumed by the discussion privilege/exclusion helpers as a global
# fallback; the site configuration written by the fixture repeats it for the
# request-time configuration path.
DISCUSSION_EXCLUDE = []

ALLOWED_HOSTS = list(ALLOWED_HOSTS)
for host in ('localhost', '127.0.0.1'):
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

CACHES = {
    alias: {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': '{}:{}'.format(DISCUSSION_NAMESPACE, alias),
    }
    for alias in CACHES
}

DATABASES = copy.deepcopy(DATABASES)
for alias, database in DATABASES.items():
    database['NAME'] = (
        DISCUSSION_SQL_HISTORY_DATABASE
        if alias == 'student_module_history'
        else DISCUSSION_SQL_DATABASE
    )
    database['USER'] = DISCUSSION_SQL_USER
    database['PASSWORD'] = DISCUSSION_SQL_PASSWORD
    database['CONN_MAX_AGE'] = 0

search_url = urlparse(DISCUSSION_SEARCH_SERVER)
ELASTIC_SEARCH_CONFIG = [{
    'host': search_url.hostname,
    'port': search_url.port or 9200,
    'use_ssl': search_url.scheme == 'https',
}]

DOC_STORE_CONFIG = copy.deepcopy(DOC_STORE_CONFIG)
DOC_STORE_CONFIG.update({
    'db': '{}_edxapp'.format(DISCUSSION_NAMESPACE),
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
        'db': '{}_xcontent'.format(DISCUSSION_NAMESPACE),
        'user': None,
        'password': None,
    })
