# -*- coding: utf-8 -*-
"""Disposable LMS settings for the frozen C2 production asset build."""
from __future__ import absolute_import, division, print_function, unicode_literals

import os

from .test import *  # noqa: F401,F403


INSTALLED_APPS = [app for app in list(INSTALLED_APPS) if not app.startswith('edx_proctoring')]
for _asset_app in (
        'openedx.core.djangoapps.schedules.apps.SchedulesConfig',
        'openedx.core.djangoapps.bookmarks.apps.BookmarksConfig',
        'openedx.core.djangoapps.theming.apps.ThemingConfig',
        'edx_proctoring.apps.EdxProctoringConfig',
        'lms.djangoapps.grades.apps.GradesConfig'):
    if not any(_asset_app.split('.apps', 1)[0] in app for app in INSTALLED_APPS):
        INSTALLED_APPS.append(_asset_app)


_asset_root = os.environ.get('C2_ASSET_ROOT', '/edx/var/edxapp/staticfiles')
STATIC_ROOT = os.path.join(_asset_root, 'lms')
WEBPACK_LOADER['DEFAULT']['STATS_FILE'] = os.path.join(STATIC_ROOT, 'webpack-stats.json')
