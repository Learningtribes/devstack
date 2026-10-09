# -*- coding: utf-8 -*-
"""E2 probe only: base test settings minus the duplicate edx_proctoring label.

Not a fix. edx-proctoring 1.5.7 registers EdxProctoringConfig through the
lms/cms.djangoapp plugin entry point while Platform OPTIONAL_APPS / CMS
INSTALLED_APPS also list 'edx_proctoring'; see e2/finding-edx-proctoring-duplicate.txt.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import os

if os.environ.get('E2_PROBE_SERVICE') == 'cms':
    from cms.envs.test import *  # noqa: F401,F403
else:
    from lms.envs.test import *  # noqa: F401,F403

INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'edx_proctoring']
