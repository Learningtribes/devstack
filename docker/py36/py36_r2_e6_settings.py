# -*- coding: utf-8 -*-
"""R2-preview E6 browser-gate settings for both runtimes.

devstack_docker plus private MySQL and Mongo clones, a private Elasticsearch
and memcached, so /auto_auth, sessions, enrollments, course writes and search
indexing never reach the shared devstack stores.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import copy
import os

if os.environ.get('SERVICE_VARIANT') == 'cms':
    from cms.envs.devstack_docker import *  # noqa: F401,F403
else:
    from lms.envs.devstack_docker import *  # noqa: F401,F403


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError('{} is required'.format(name))
    return value


E6_NAMESPACE = _required('PY36_R2_E6_NAMESPACE')
E6_CACHE_HOST = _required('PY36_R2_E6_CACHE_HOST')
E6_MYSQL_HOST = _required('PY36_R2_E6_MYSQL_HOST')
E6_MYSQL_PASSWORD = _required('PY36_R2_E6_MYSQL_ROOT_PASSWORD')
E6_MONGO_HOST = _required('PY36_R2_E6_MONGO_HOST')
E6_ES_HOST = _required('PY36_R2_E6_ES_HOST')

# devstack-only instrumentation, as in the R1 gate settings: the toolbar is
# injected into every page and covers form controls the gates click.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'debug_toolbar']
MIDDLEWARE_CLASSES = [
    middleware for middleware in MIDDLEWARE_CLASSES
    if middleware not in (
        'django_comment_client.utils.QueryCountDebugMiddleware',
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    )
]

WSGI_APPLICATION = 'r2_e6_wsgi.application'

ALLOWED_HOSTS = list(ALLOWED_HOSTS)
for host in ('localhost', '127.0.0.1'):
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

DATABASES = copy.deepcopy(DATABASES)
for database in DATABASES.values():
    database.update({'HOST': E6_MYSQL_HOST, 'PORT': '3306', 'USER': 'root', 'PASSWORD': E6_MYSQL_PASSWORD})


def _private_mongo(config):
    # The private mongod runs without --auth; the shared credentials would be
    # rejected there.
    config = dict(config, host=[E6_MONGO_HOST] if isinstance(config.get('host'), list) else E6_MONGO_HOST)
    config.pop('user', None)
    config.pop('password', None)
    return config


DOC_STORE_CONFIG = _private_mongo(DOC_STORE_CONFIG)
MODULESTORE = copy.deepcopy(MODULESTORE)
for store in MODULESTORE['default']['OPTIONS']['stores']:
    store['DOC_STORE_CONFIG'] = _private_mongo(store['DOC_STORE_CONFIG'])
CONTENTSTORE = copy.deepcopy(CONTENTSTORE)
CONTENTSTORE['DOC_STORE_CONFIG'] = _private_mongo(CONTENTSTORE['DOC_STORE_CONFIG'])
CONTENTSTORE['OPTIONS'] = _private_mongo(CONTENTSTORE['OPTIONS'])
if 'EDX_OBJECTS_MONGODB_SETTINGS' in globals():
    EDX_OBJECTS_MONGODB_SETTINGS = {
        name: _private_mongo(config) for name, config in EDX_OBJECTS_MONGODB_SETTINGS.items()
    }

ELASTIC_SEARCH_CONFIG = [{'use_ssl': False, 'host': E6_ES_HOST, 'port': 9200}]

# LMS and CMS share one namespace so the LMS /auto_auth session also
# authenticates Studio, as on the stock devstack.
CACHES = copy.deepcopy(CACHES)
for alias, cache in CACHES.items():
    if cache.get('BACKEND', '').endswith('MemcachedCache'):
        cache['LOCATION'] = ['{}:11211'.format(E6_CACHE_HOST)]
        cache['KEY_PREFIX'] = '{}_{}'.format(E6_NAMESPACE, cache.get('KEY_PREFIX', alias))

# No gate-owned broker: tasks run inline and nothing reaches the shared RabbitMQ.
CELERY_ALWAYS_EAGER = True
BROKER_URL = 'memory://'
CELERY_BROKER_URL = BROKER_URL

# With PY36_R2_E6_WITH_BROKER=1 the LMS side (server, scripts, worker) uses the
# stack's own RabbitMQ. Exchange, queue names and routing keys follow the R1
# grading gate settings, whose provisioner asserts on them.
E6_RABBIT_HOST = os.environ.get('PY36_R2_E6_RABBIT_HOST')
if E6_RABBIT_HOST:
    RABBIT_CONTAINER = E6_RABBIT_HOST
    RABBIT_VHOST = E6_NAMESPACE
    RABBIT_USER = _required('PY36_R2_E6_RABBIT_USER')
    RABBIT_PASSWORD = _required('PY36_R2_E6_RABBIT_PASSWORD')
    BROKER_URL = 'amqp://{}:{}@{}:5672/{}'.format(RABBIT_USER, RABBIT_PASSWORD, RABBIT_CONTAINER, RABBIT_VHOST)
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
    CELERY_DEFAULT_EXCHANGE = '{}.edx.core'.format(E6_NAMESPACE)
    CELERY_DEFAULT_EXCHANGE_TYPE = 'direct'
    CELERY_DEFAULT_QUEUE = '{}.default'.format(E6_NAMESPACE)
    CELERY_DEFAULT_ROUTING_KEY = CELERY_DEFAULT_QUEUE
    CELERY_QUEUE_HA_POLICY = 'all'
    CELERY_CREATE_MISSING_QUEUES = False
    GRADING_QUEUES = {
        role: '{}.{}'.format(E6_NAMESPACE, role)
        for role in ('high', 'low', 'default', 'high_mem', 'grade', 'progress')
    }
    CELERY_QUEUES = {
        queue: {'exchange': CELERY_DEFAULT_EXCHANGE, 'exchange_type': 'direct', 'routing_key': queue}
        for queue in GRADING_QUEUES.values()
    }
    RECALCULATE_GRADES_ROUTING_KEY = GRADING_QUEUES['grade']
    RECALCULATE_PROGRESS_ROUTING_KEY = GRADING_QUEUES['progress']
    POLICY_CHANGE_GRADES_ROUTING_KEY = GRADING_QUEUES['grade']

FEATURES = copy.deepcopy(FEATURES)
FEATURES.update({
    'AUTOMATIC_AUTH_FOR_TESTING': True,
    'RESTRICT_AUTOMATIC_AUTH': False,
    'ALLOW_PUBLIC_ACCOUNT_CREATION': True,
    'CERTIFICATES_HTML_VIEW': True,
    # Off unless the stack runs its own comments service: auto_auth would
    # otherwise create forum users in the shared one.
    'ENABLE_DISCUSSION_SERVICE': bool(os.environ.get('PY36_R2_E6_FORUM_URL')),
})

if FEATURES['ENABLE_DISCUSSION_SERVICE']:
    COMMENTS_SERVICE_URL = os.environ['PY36_R2_E6_FORUM_URL']
    COMMENTS_SERVICE_KEY = _required('COMMENTS_SERVICE_KEY')
    # Global fallback for the discussion exclusion helpers; the gate fixture
    # sets the same value on the site configuration.
    DISCUSSION_EXCLUDE = []
