# -*- coding: utf-8 -*-
"""Isolated LMS settings for the Studio edit/publish browser gate."""
from __future__ import absolute_import, division, print_function, unicode_literals

from lms.envs.devstack_docker import *  # noqa: F401,F403

from p1b_studio_publish_settings import configure


configure(globals(), 'lms')
