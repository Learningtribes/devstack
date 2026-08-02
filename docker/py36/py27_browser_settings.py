# -*- coding: utf-8 -*-
"""Isolation overlay for the disposable Python 2 browser control."""
from __future__ import absolute_import, division, print_function, unicode_literals

import copy
import os

from lms.envs.devstack_docker import *  # noqa: F401,F403
from xmodule.modulestore.modulestore_settings import update_module_store_settings


BROWSER_NAMESPACE = os.environ.get(
    'PY36_R1_BROWSER_NAMESPACE',
    'py36_r1_p1b_dashboard_reviewfix_py27',
)

INSTALLED_APPS = list(INSTALLED_APPS)
if not any(app.startswith('edx_proctoring') for app in INSTALLED_APPS):
    INSTALLED_APPS.append('edx_proctoring.apps.EdxProctoringConfig')

FEATURES = copy.deepcopy(FEATURES)
FEATURES.update({
    'ALLOW_PUBLIC_ACCOUNT_CREATION': True,
    'RESTRICT_AUTOMATIC_AUTH': False,
})

CACHES = {
    alias: {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': '{}:{}'.format(BROWSER_NAMESPACE, alias),
    }
    for alias in CACHES
}

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
