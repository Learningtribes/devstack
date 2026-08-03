# -*- coding: utf-8 -*-
"""Isolated non-eager LMS/worker settings for the P1-B grading gate."""
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


GRADING_RUNTIME = _required('PY36_R1_GRADING_RUNTIME')
GRADING_NAMESPACE = _required('PY36_R1_GRADING_NAMESPACE')
SITE_NAME = _required('PY36_R1_GRADING_SITE_DOMAIN')
SQL_DATABASE = _required('PY36_R1_GRADING_SQL_DATABASE')
SQL_HISTORY_DATABASE = _required('PY36_R1_GRADING_SQL_HISTORY_DATABASE')
SQL_USER = _required('PY36_R1_GRADING_SQL_USER')
SQL_PASSWORD = _required('PY36_R1_GRADING_SQL_PASSWORD')
MONGO_MODULESTORE_DATABASE = _required('PY36_R1_GRADING_MONGO_MODULESTORE_DATABASE')
MONGO_CONTENTSTORE_DATABASE = _required('PY36_R1_GRADING_MONGO_CONTENTSTORE_DATABASE')
MONGO_USER = _required('PY36_R1_GRADING_MONGO_USER')
MONGO_PASSWORD = _required('PY36_R1_GRADING_MONGO_PASSWORD')
MONGO_CONTAINER = _required('PY36_R1_GRADING_MONGO_CONTAINER')
RABBIT_CONTAINER = _required('PY36_R1_GRADING_RABBIT_CONTAINER')
RABBIT_USER = _required('PY36_R1_GRADING_RABBIT_USER')
RABBIT_PASSWORD = _required('PY36_R1_GRADING_RABBIT_PASSWORD')
CACHE_CONTAINER = _required('PY36_R1_GRADING_CACHE_CONTAINER')

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
STATIC_ROOT = os.path.join('/tmp', GRADING_NAMESPACE, 'staticfiles-output')
STATICFILES_DIRS = [COLLECTED_STATIC_ROOT] + list(STATICFILES_DIRS)

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

# Every cache alias points at the gate-owned daemon and carries a gate prefix.
CACHES = copy.deepcopy(CACHES)
for alias, cache in CACHES.items():
    backend = cache.get('BACKEND', '')
    if backend.endswith('LocMemCache'):
        cache['LOCATION'] = '{}:{}'.format(GRADING_NAMESPACE, alias)
    else:
        cache['LOCATION'] = ['{}:11211'.format(CACHE_CONTAINER)]
    cache['KEY_PREFIX'] = '{}_{}'.format(GRADING_NAMESPACE, cache.get('KEY_PREFIX', alias))

RABBIT_VHOST = GRADING_NAMESPACE
BROKER_URL = 'amqp://{}:{}@{}:5672/{}'.format(
    RABBIT_USER,
    RABBIT_PASSWORD,
    RABBIT_CONTAINER,
    RABBIT_VHOST,
)
CELERY_BROKER_URL = BROKER_URL
CELERY_RESULT_BACKEND = 'rpc://'
CELERY_ALWAYS_EAGER = False
CELERY_TASK_ALWAYS_EAGER = False
BROKER_HEARTBEAT = 30.0
BROKER_HEARTBEAT_CHECKRATE = 2
CELERY_SEND_EVENTS = True
CELERY_SEND_TASK_SENT_EVENT = True
CELERY_TRACK_STARTED = True
CELERYD_PREFETCH_MULTIPLIER = 1
CELERY_DEFAULT_EXCHANGE = '{}.edx.core'.format(GRADING_NAMESPACE)
CELERY_DEFAULT_EXCHANGE_TYPE = 'direct'
CELERY_DEFAULT_QUEUE = '{}.default'.format(GRADING_NAMESPACE)
CELERY_DEFAULT_ROUTING_KEY = CELERY_DEFAULT_QUEUE
CELERY_QUEUE_HA_POLICY = 'all'
CELERY_CREATE_MISSING_QUEUES = False

GRADING_QUEUES = {
    'high': '{}.high'.format(GRADING_NAMESPACE),
    'low': '{}.low'.format(GRADING_NAMESPACE),
    'default': '{}.default'.format(GRADING_NAMESPACE),
    'high_mem': '{}.high_mem'.format(GRADING_NAMESPACE),
    'grade': '{}.grade'.format(GRADING_NAMESPACE),
    'progress': '{}.progress'.format(GRADING_NAMESPACE),
}
CELERY_QUEUES = {
    queue: {
        'exchange': CELERY_DEFAULT_EXCHANGE,
        'exchange_type': 'direct',
        'routing_key': queue,
    }
    for queue in GRADING_QUEUES.values()
}
RECALCULATE_GRADES_ROUTING_KEY = GRADING_QUEUES['grade']
RECALCULATE_PROGRESS_ROUTING_KEY = GRADING_QUEUES['progress']
POLICY_CHANGE_GRADES_ROUTING_KEY = GRADING_QUEUES['grade']

SITE_ID = globals().get('SITE_ID', 1)
