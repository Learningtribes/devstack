# -*- coding: utf-8 -*-
"""R2-preview E4 service settings: devstack_docker plus an isolated broker and cache."""
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


E4_SERVICE = os.environ.get('SERVICE_VARIANT', 'lms')
E4_NAMESPACE = _required('PY36_R2_E4_NAMESPACE')
E4_CACHE_HOST = _required('PY36_R2_E4_CACHE_HOST')

ALLOWED_HOSTS = list(ALLOWED_HOSTS)
for host in ('localhost', '127.0.0.1'):
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

# Python 2.7 services share the devstack memcached; Python 3 pickles must not
# reach it, so every memcached alias moves to the gate-owned daemon.
CACHES = copy.deepcopy(CACHES)
for alias, cache in CACHES.items():
    if cache.get('BACKEND', '').endswith('MemcachedCache'):
        cache['LOCATION'] = ['{}:11211'.format(E4_CACHE_HOST)]
        cache['KEY_PREFIX'] = '{}_{}'.format(E4_NAMESPACE, cache.get('KEY_PREFIX', alias))

# cached_db would write Python 3 pickled sessions into the shared MySQL table.
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

BROKER_URL = 'amqp://{}:{}@{}:5672/{}'.format(
    _required('PY36_R2_E4_RABBIT_USER'),
    _required('PY36_R2_E4_RABBIT_PASSWORD'),
    _required('PY36_R2_E4_RABBIT_HOST'),
    _required('PY36_R2_E4_RABBIT_VHOST'),
)
CELERY_BROKER_URL = BROKER_URL
CELERY_RESULT_BACKEND = 'rpc://'
CELERY_ALWAYS_EAGER = False
BROKER_HEARTBEAT = 30.0
BROKER_HEARTBEAT_CHECKRATE = 2
CELERYD_PREFETCH_MULTIPLIER = 1
CELERY_DEFAULT_EXCHANGE = '{}.{}'.format(E4_NAMESPACE, E4_SERVICE)
CELERY_DEFAULT_EXCHANGE_TYPE = 'direct'
CELERY_DEFAULT_QUEUE = '{}.{}.default'.format(E4_NAMESPACE, E4_SERVICE)
CELERY_DEFAULT_ROUTING_KEY = CELERY_DEFAULT_QUEUE
CELERY_QUEUES = {
    CELERY_DEFAULT_QUEUE: {
        'exchange': CELERY_DEFAULT_EXCHANGE,
        'exchange_type': 'direct',
        'routing_key': CELERY_DEFAULT_QUEUE,
    },
}
