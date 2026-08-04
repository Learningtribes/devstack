# -*- coding: utf-8 -*-
"""Runner-only isolation overlay for the Hawthorn LMS test settings."""
from __future__ import absolute_import, division, print_function, unicode_literals

import copy
import os

from path import Path as path
from six import string_types

if os.environ.get('PY36_R1_TEST_SERVICE') == 'cms':
    from cms.envs.test import *  # noqa: F401,F403
else:
    from lms.envs.test import *  # noqa: F401,F403


# The m5-fixed Python 2 base carries edx-proctoring 1.4 without the plugin
# metadata used by the current Python 3 runtime. Keep the runner settings
# equivalent by registering the installed app when the entry point cannot do
# it for us.
try:
    import edx_proctoring  # noqa: F401
except ImportError:
    pass
else:
    if not any(app.startswith('edx_proctoring') for app in INSTALLED_APPS):
        INSTALLED_APPS.append('edx_proctoring')

# CMS contentstore tests import xblock_config models directly. The LMS test
# settings do not normally install this CMS-only app, so register its exact
# AppConfig for the shared runner overlay.
if not any(app.startswith('xblock_config') for app in INSTALLED_APPS):
    INSTALLED_APPS.append('xblock_config.apps.XBlockConfig')

# ORA2 handler tests use the xblock-sdk workbench runtime and its state model.
# Keep this test-only app scoped to the ORA2 profile.
if os.environ.get('PY36_R1_ORA2_TESTS') == '1':
    if 'workbench' not in INSTALLED_APPS:
        INSTALLED_APPS.append('workbench')
    WORKBENCH = {'services': {}}


RUNNER_NAMESPACE = os.environ.get('PY36_R1_TEST_NAMESPACE', 'py36-r1-p0b')
RUNNER_MONGO_DB_PREFIX = os.environ.get('PY36_R1_MONGO_DB_PREFIX', RUNNER_NAMESPACE)
RUNNER_TEST_ROOT = os.environ.get('PY36_R1_TEST_ROOT', '/runner/test_root')
TEST_ROOT = path(RUNNER_TEST_ROOT)

# Keep all file-backed test state on the disposable runner filesystem.
STATIC_ROOT = TEST_ROOT / 'staticfiles'
STATUS_MESSAGE_PATH = TEST_ROOT / 'status_message.json'
COURSES_ROOT = TEST_ROOT / 'data'
DATA_DIR = COURSES_ROOT
GIT_REPO_DIR = TEST_ROOT / 'course_repos'
MEDIA_ROOT = TEST_ROOT / 'uploads'
FILE_UPLOAD_TEMP_DIR = TEST_ROOT / 'uploads'
WEBPACK_LOADER = copy.deepcopy(WEBPACK_LOADER)
WEBPACK_LOADER['DEFAULT']['STATS_FILE'] = STATIC_ROOT / 'webpack-stats.json'

# Never use a Devstack MySQL schema for a runner. Each disposable container has
# its own SQLite files, even if tests create the database.
DATABASES = copy.deepcopy(DATABASES)
for database_alias, database in DATABASES.items():
    database['ENGINE'] = 'django.db.backends.sqlite3'
    database['NAME'] = str(TEST_ROOT / 'db' / '{}.sqlite3'.format(database_alias))

# The base test settings use DummyCache/LocMemCache. Add a runner-specific
# location/key prefix so an accidental cache backend override cannot collide.
CACHES = copy.deepcopy(CACHES)
for cache_name, cache in CACHES.items():
    backend = cache.get('BACKEND', '')
    if backend.endswith('LocMemCache'):
        cache['LOCATION'] = '{}:{}'.format(RUNNER_NAMESPACE, cache_name)
    elif backend.endswith('DummyCache'):
        cache['KEY_PREFIX'] = RUNNER_NAMESPACE


def _mongo_database(name):
    return '{}_{}'.format(RUNNER_MONGO_DB_PREFIX, name)


# Keep any Mongo-backed test data in a namespace dedicated to this runner.
DOC_STORE_CONFIG = copy.deepcopy(DOC_STORE_CONFIG)
DOC_STORE_CONFIG.update({
    'db': _mongo_database('xmodule'),
    'collection': 'modulestore',
})
MODULESTORE = copy.deepcopy(MODULESTORE)
update_module_store_settings(
    MODULESTORE,
    doc_store_settings=DOC_STORE_CONFIG,
    module_store_options={'fs_root': str(COURSES_ROOT)},
)
CONTENTSTORE = copy.deepcopy(CONTENTSTORE)
if CONTENTSTORE:
    CONTENTSTORE.setdefault('DOC_STORE_CONFIG', {}).update({
        'db': _mongo_database('xcontent'),
        'collection': 'contentstore',
    })
EDX_OBJECTS_MONGODB_SETTINGS = copy.deepcopy(EDX_OBJECTS_MONGODB_SETTINGS)
if 'programs' in EDX_OBJECTS_MONGODB_SETTINGS:
    EDX_OBJECTS_MONGODB_SETTINGS['programs']['db'] = _mongo_database('programs')
if 'MONGODB_LOG' in globals() and MONGODB_LOG:
    MONGODB_LOG = copy.deepcopy(MONGODB_LOG)
    MONGODB_LOG['db'] = _mongo_database('xlog')


def _queue_name(value):
    if isinstance(value, string_types) and value.startswith(RUNNER_NAMESPACE + '.'):
        return value
    if isinstance(value, string_types):
        return '{}.{}'.format(RUNNER_NAMESPACE, value)
    return value


# Celery is eager for the test settings. The memory broker and namespaced queue
# values are a second guard if a focused test temporarily disables eager mode.
CELERY_ALWAYS_EAGER = True
BROKER_URL = 'memory://'
CELERY_BROKER_URL = BROKER_URL
CELERY_BROKER_VHOST = RUNNER_NAMESPACE
CELERY_DEFAULT_QUEUE = _queue_name(CELERY_DEFAULT_QUEUE)
CELERY_DEFAULT_ROUTING_KEY = _queue_name(CELERY_DEFAULT_ROUTING_KEY)
CELERY_QUEUES = {
    _queue_name(queue): copy.deepcopy(options)
    for queue, options in CELERY_QUEUES.items()
}
for queue_setting in (
        'CERT_QUEUE',
        'ACE_ROUTING_KEY',
        'GRADES_DOWNLOAD_ROUTING_KEY',
        'CREDENTIALS_GENERATION_ROUTING_KEY',
        'RECALCULATE_GRADES_ROUTING_KEY',
        'RECALCULATE_PROGRESS_ROUTING_KEY',
        'POLICY_CHANGE_GRADES_ROUTING_KEY'):
    if queue_setting in globals():
        globals()[queue_setting] = _queue_name(globals()[queue_setting])
