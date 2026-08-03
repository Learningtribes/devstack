# -*- coding: utf-8 -*-
"""Isolated CMS settings for the Studio edit/publish browser gate."""
from __future__ import absolute_import, division, print_function, unicode_literals

from cms.envs.devstack_docker import *  # noqa: F401,F403

from p1b_studio_publish_settings import configure


configure(globals(), 'cms')
