# -*- coding: utf-8 -*-
"""Isolated LMS settings for the P1-B SCORM render gate."""
from __future__ import absolute_import, division, print_function, unicode_literals

import copy
import os

from lms.envs.devstack_docker import *  # noqa: F401,F403
from xmodule.modulestore.modulestore_settings import update_module_store_settings


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError('{} is required'.format(name))
    return value


SCORM_GATE_RUNTIME = _required('PY36_R1_SCORM_RUNTIME')
SCORM_GATE_NAMESPACE = _required('PY36_R1_SCORM_NAMESPACE')
SITE_NAME = _required('PY36_R1_SCORM_SITE_DOMAIN')
SQL_DATABASE = _required('PY36_R1_SCORM_SQL_DATABASE')
SQL_HISTORY_DATABASE = _required('PY36_R1_SCORM_SQL_HISTORY_DATABASE')
SQL_USER = _required('PY36_R1_SCORM_SQL_USER')
SQL_PASSWORD = _required('PY36_R1_SCORM_SQL_PASSWORD')
MONGO_MODULESTORE_DATABASE = _required('PY36_R1_SCORM_MONGO_MODULESTORE_DATABASE')
MONGO_CONTENTSTORE_DATABASE = _required('PY36_R1_SCORM_MONGO_CONTENTSTORE_DATABASE')
MONGO_USER = _required('PY36_R1_SCORM_MONGO_USER')
MONGO_PASSWORD = _required('PY36_R1_SCORM_MONGO_PASSWORD')
MONGO_CONTAINER = _required('PY36_R1_SCORM_MONGO_CONTAINER')
SCORM_FS_ROOT = _required('PY36_R1_SCORM_FS_ROOT')

LMS_BASE = SITE_NAME
LMS_ROOT_URL = 'http://{}'.format(SITE_NAME)
LMS_INTERNAL_ROOT_URL = LMS_ROOT_URL

ALLOWED_HOSTS = list(ALLOWED_HOSTS)
for host in ('localhost', '127.0.0.1'):
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

FEATURES = copy.deepcopy(FEATURES)
FEATURES.update({
    'ALLOW_AUTOMATED_SIGNUPS': True,
    'ALLOW_PUBLIC_ACCOUNT_CREATION': True,
    'AUTOMATIC_AUTH_FOR_TESTING': True,
    'COURSES_ARE_BROWSABLE': True,
    'ENABLE_DISCUSSION_SERVICE': False,
    'ENABLE_LAST_ACTIVITY': True,
    'RESTRICT_AUTOMATIC_AUTH': False,
})

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

COLLECTED_STATIC_ROOT = STATIC_ROOT
STATIC_ROOT = os.path.join('/tmp', SCORM_GATE_NAMESPACE, 'staticfiles-output')
STATICFILES_DIRS = [COLLECTED_STATIC_ROOT, ('djpyfs', SCORM_FS_ROOT)] + list(STATICFILES_DIRS)
DJFS = {
    'type': 'osfs',
    'directory_root': SCORM_FS_ROOT,
    'url_root': '/static/djpyfs',
}

DATABASES = copy.deepcopy(DATABASES)
for alias, database in DATABASES.items():
    database['NAME'] = SQL_HISTORY_DATABASE if alias == 'student_module_history' else SQL_DATABASE
    database['USER'] = SQL_USER
    database['PASSWORD'] = SQL_PASSWORD
    database['HOST'] = 'edx.devstack.mysql'
    database['PORT'] = '3306'
    database['CONN_MAX_AGE'] = 0

DOC_STORE_CONFIG = copy.deepcopy(DOC_STORE_CONFIG)
DOC_STORE_CONFIG.update({
    'db': MONGO_MODULESTORE_DATABASE,
    'host': [MONGO_CONTAINER],
    'user': MONGO_USER,
    'password': MONGO_PASSWORD,
})
MODULESTORE = copy.deepcopy(MODULESTORE)
update_module_store_settings(
    MODULESTORE,
    doc_store_settings={
        'db': MONGO_MODULESTORE_DATABASE,
        'host': [MONGO_CONTAINER],
        'user': MONGO_USER,
        'password': MONGO_PASSWORD,
    },
    module_store_options={'fs_root': '/edx/var/edxapp/data'},
)

CONTENTSTORE = {
    'ENGINE': 'xmodule.contentstore.mongo.MongoContentStore',
    'DOC_STORE_CONFIG': {
        'db': MONGO_CONTENTSTORE_DATABASE,
        'host': [MONGO_CONTAINER],
        'port': 27017,
        'user': MONGO_USER,
        'password': MONGO_PASSWORD,
    },
}

MONGO_METADATA_INHERITANCE = copy.deepcopy(globals().get('MONGO_METADATA_INHERITANCE', {}))
if isinstance(MONGO_METADATA_INHERITANCE, dict):
    MONGO_METADATA_INHERITANCE.update({
        'host': [MONGO_CONTAINER],
        'db': MONGO_MODULESTORE_DATABASE,
        'user': MONGO_USER,
        'password': MONGO_PASSWORD,
    })

CACHES = {
    alias: {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': '{}:{}'.format(SCORM_GATE_NAMESPACE, alias),
    }
    for alias in CACHES
}

CELERY_ALWAYS_EAGER = True
CELERY_TASK_ALWAYS_EAGER = True
COURSE_REVIEWS_TOOL_PROVIDER_FRAGMENT_NAME = None
COURSE_REVIEWS_TOOL_PROVIDER_PLATFORM_KEY = None
SITE_ID = globals().get('SITE_ID', 1)
