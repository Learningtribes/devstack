# -*- coding: utf-8 -*-
"""R2-preview E6 browser-gate settings for both runtimes.

devstack_docker plus a private MySQL clone and memcached, so /auto_auth,
sessions and enrollments never write to the shared devstack stores.
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

ALLOWED_HOSTS = list(ALLOWED_HOSTS)
for host in ('localhost', '127.0.0.1'):
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

DATABASES = copy.deepcopy(DATABASES)
for database in DATABASES.values():
    database.update({'HOST': E6_MYSQL_HOST, 'PORT': '3306', 'USER': 'root', 'PASSWORD': E6_MYSQL_PASSWORD})

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
    # The comments service and its Mongo are shared; auto_auth would create
    # forum users there.
    'ENABLE_DISCUSSION_SERVICE': False,
})
