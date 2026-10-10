# -*- coding: utf-8 -*-
"""Run the R1 SCORM render provisioner against an E6 private-store stack.

E6 serves the canonical ``localhost:18000`` origin, whose cloned Site and
SiteConfiguration the R1 provision updates in place (``get_or_create``);
provision then unthemes that site, as the ORA2 and grading gates do (R1 gates
ran on unthemed per-gate sites). The expected scormxblock commit, tree and
module hash are set per run (the Python 2.7 image installs an older commit),
and ``PY36_R2_E6_SCORM_SOURCE_ROOT`` names the read-only overlay checkout the
package must be imported from. The host verifies the mounted Platform commit
and passes it in.
usage: r2-e6-scorm.py {identity|provision|preflight|postflight}
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import imp
import os

R1 = imp.load_source(
    'r1_scorm_provision',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'provision-p1b-scorm-render.py'),
)
for _runtime, _fixture in R1.RUNTIME_FIXTURES.items():
    _fixture.update({
        'site_domain': 'localhost:18000',
        'namespace': 'py36-r2-e6-{}'.format(_runtime),
    })
R1.SCORM_COMMIT = os.environ['PY36_R2_E6_SCORM_COMMIT']
R1.SCORM_TREE = os.environ['PY36_R2_E6_SCORM_TREE']
R1.SCORM_MODULE_SHA256 = os.environ['PY36_R2_E6_SCORM_MODULE_SHA256']
R1.SCORM_SOURCE_ROOT = os.environ.get('PY36_R2_E6_SCORM_SOURCE_ROOT') or None

from django.conf import settings  # noqa: E402
from django.contrib.sites.models import Site  # noqa: E402
from openedx.core.djangoapps.theming.models import SiteTheme  # noqa: E402

_r1_provision = R1.provision


def _provision_unthemed(fixture):
    _r1_provision(fixture)
    site = Site.objects.get(domain=fixture['site_domain'])
    themes = SiteTheme.objects.filter(site=site)
    removed = sorted(themes.values_list('theme_dir_name', flat=True))
    themes.delete()
    if SiteTheme.objects.filter(site=site).exists():
        raise RuntimeError('site theme is still set for {}'.format(site.domain))
    print('E6_SCORM_SITE site_id={} domain={} name={!r} unthemed={} djfs={}'.format(
        site.id, site.domain, site.name, removed, sorted(settings.DJFS.items()),
    ))


R1.provision = _provision_unthemed

if __name__ == '__main__':
    R1.main()
