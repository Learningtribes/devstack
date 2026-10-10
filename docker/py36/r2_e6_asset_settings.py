# -*- coding: utf-8 -*-
"""R2-preview E6 asset-build settings: devstack_docker without a database server.

Copied into the disposable clone as lms/envs/r2_e6_asset.py and
cms/envs/r2_e6_asset.py so every static setting matches the E6 runtime.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

from .devstack_docker import *  # noqa: F401,F403

# The build runs with --network none. Django's MySQL system checks would
# otherwise connect to the shared devstack MySQL just to read its version.
DATABASES = {alias: {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'} for alias in DATABASES}
