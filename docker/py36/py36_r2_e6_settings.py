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
