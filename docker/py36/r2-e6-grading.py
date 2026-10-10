# -*- coding: utf-8 -*-
"""Run the R1 grading mutation provisioner against an E6 private-store stack.

E6 serves the canonical ``localhost:18000`` origin, so the gate site row is
that domain rather than R1's per-gate port; queues live under the stack
namespace on its private RabbitMQ. The R1 spec asserts the unit title is
visible, which the hawthorn theme hides (``.xblock .unit-title``), so provision
also unthemes that site in the private clone, matching R1's unthemed gate site.
usage: r2-e6-grading.py {provision|preflight|reset|midcondition|postflight}
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import imp
import os

R1 = imp.load_source(
    'r1_grading_provision',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'provision-p1b-grading-mutation.py'),
)
for _runtime, _fixture in R1.RUNTIME_FIXTURES.items():
    _fixture.update({
        'site_domain': 'localhost:18000',
        'namespace': 'py36-r2-e6-{}'.format(_runtime),
    })

from openedx.core.djangoapps.theming.models import SiteTheme  # noqa: E402

_r1_ensure_site = R1._ensure_site


def _ensure_unthemed_site(fixture):
    _r1_ensure_site(fixture)
    themes = SiteTheme.objects.filter(site__domain=fixture['site_domain'])
    removed = sorted(themes.values_list('theme_dir_name', flat=True))
    themes.delete()
    if SiteTheme.objects.filter(site__domain=fixture['site_domain']).exists():
        raise RuntimeError('site theme is still set for {}'.format(fixture['site_domain']))
    print('E6_GRADING_UNTHEMED site={} removed={}'.format(fixture['site_domain'], removed))


R1._ensure_site = _ensure_unthemed_site

if __name__ == '__main__':
    R1.main()
