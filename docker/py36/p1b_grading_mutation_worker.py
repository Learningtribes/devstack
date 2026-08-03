# -*- coding: utf-8 -*-
"""Run the isolated grading worker with a heartbeat-aware sync loop."""
from __future__ import absolute_import, division, print_function, unicode_literals

import os
import socket
import sys

import django

django.setup()

from celery import bootsteps  # noqa: E402
from celery.worker import state  # noqa: E402
from celery.worker import WorkController  # noqa: E402
from django.conf import settings  # noqa: E402

from lms.celery import APP  # noqa: E402
from lms.djangoapps.grades.tasks import (  # noqa: E402
    calculate_course_progress,
    recalculate_subsection_grade_v3,
)


def grading_sync_loop(obj, connection, consumer, blueprint, hub, qos, heartbeat, clock,
                      hbrate=2.0, **kwargs):
    """Keep the old py-amqp connection alive while consuming with a timeout."""
    on_task_received = obj.create_task_handler()
    consumer.register_callback(on_task_received)
    consumer.consume()
    obj.on_ready()

    while blueprint.state == bootsteps.RUN and obj.connection:
        state.maybe_shutdown()
        if qos.prev != qos.value:
            qos.update()
        connection.heartbeat_check(rate=hbrate)
        try:
            connection.drain_events(timeout=1.0)
        except socket.timeout:
            pass
        except socket.error:
            if blueprint.state == bootsteps.RUN:
                raise


def main():
    required = (
        recalculate_subsection_grade_v3.name,
        calculate_course_progress.name,
    )
    missing = [name for name in required if name not in APP.tasks]
    if missing:
        raise RuntimeError('missing required grading tasks: {}'.format(missing))

    controller = WorkController(
        app=APP,
        hostname='{}@%h'.format(os.environ.get(
            'PY36_R1_GRADING_WORKER_HOSTNAME', 'p1b-grading-mutation-worker'
        )),
        loglevel='INFO',
        pool='solo',
        concurrency=1,
        use_eventloop=False,
        queues=(settings.GRADING_QUEUES['grade'], settings.GRADING_QUEUES['progress']),
        without_mingle=True,
        without_gossip=True,
        without_heartbeat=False,
    )
    controller.consumer.amqheartbeat = settings.BROKER_HEARTBEAT
    controller.consumer.loop = grading_sync_loop
    sys.stdout.write(
        'P1B_GRADING_WORKER_READY queues={} required={} broker_heartbeat={} loop=sync\n'.format(
            settings.GRADING_QUEUES,
            required,
            settings.BROKER_HEARTBEAT,
        )
    )
    sys.stdout.flush()
    controller.start()


if __name__ == '__main__':
    main()
