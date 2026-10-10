# -*- coding: utf-8 -*-
"""Run the R1 discussion provisioner against an E6 private-store stack.

E6 serves the canonical ``localhost:18000`` origin, so the gate site row is
that domain rather than R1's per-gate port.
usage: r2-e6-discussion.py {provision|reset|postflight}
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import imp
import os

R1 = imp.load_source(
    'r1_discussion_provision',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'provision-p1b-discussion-read-write.py'),
)
for _runtime, _fixture in R1.RUNTIME_FIXTURES.items():
    _fixture.update({
        'site_domain': 'localhost:18000',
        'namespace': 'py36-r2-e6-{}'.format(_runtime),
    })

if __name__ == '__main__':
    R1.main()
