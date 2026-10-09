# -*- coding: utf-8 -*-
"""Submit E4 probe tasks to the isolated worker: py36_r2_e4_tasks.py <step>..."""
from __future__ import absolute_import, division, print_function, unicode_literals

import sys

import django

django.setup()

from django.conf import settings  # noqa: E402

from lms.celery import APP  # noqa: E402

TASKS = {
    'heartbeat': 'openedx.core.djangoapps.heartbeat.tasks.sample_task',
    'success': 'py36_r2_e4.success',
    'controlled_failure': 'py36_r2_e4.controlled_failure',
}


def submit(step):
    result = APP.send_task(
        TASKS[step.split(':')[0]],
        queue=settings.CELERY_DEFAULT_QUEUE,
        exchange=settings.CELERY_DEFAULT_EXCHANGE,
        routing_key=settings.CELERY_DEFAULT_ROUTING_KEY,
    )
    value = result.get(timeout=60, propagate=False)
    print('TASK step={} id={} state={} result={!r} traceback={}'.format(
        step, result.id, result.state, value, 'present' if result.traceback else 'none',
    ))
    return result.state


def inspect():
    control = APP.control.inspect(timeout=5)
    for name in ('active', 'reserved', 'scheduled'):
        print('INSPECT {}={}'.format(name, getattr(control, name)()))
    registered = control.registered() or {}
    print('INSPECT registered={}'.format({worker: len(tasks) for worker, tasks in registered.items()}))
    for worker, tasks in registered.items():
        print('INSPECT probe_tasks_registered={}'.format(all(name in tasks for name in TASKS.values())))


def main(steps):
    expected = {'heartbeat': 'SUCCESS', 'success': 'SUCCESS', 'controlled_failure': 'FAILURE'}
    failed = False
    for step in steps:
        if step == 'inspect':
            inspect()
            continue
        failed |= submit(step) != expected[step.split(':')[0]]
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
