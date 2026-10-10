# -*- coding: utf-8 -*-
"""Run the R1 ORA2 staff-assessment provisioner against an E6 private-store stack.

E6 serves the canonical ``localhost:18000`` origin: R1 renames Site
``settings.SITE_ID`` to its per-gate port, which here would rename and delete
cloned canonical rows, so provision merges the gate values into the existing
``localhost:18000`` configuration instead and unthemes that site (the R1 spec
asserts the unit title the hawthorn theme hides). Queues are the stack's
``GRADING_QUEUES`` on its private RabbitMQ. The host verifies the mounted
Platform commit (the container sees a worktree whose git directory is not
mounted) and passes it in; the expected ORA2 commit is set per run.
usage: r2-e6-ora2.py {identity|provision|preflight|submission-ready|staff-lease|postflight|reset}
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import imp
import os

R1 = imp.load_source(
    'r1_ora2_provision',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'provision-p1b-ora2-assessment.py'),
)
for _runtime, _fixture in R1.RUNTIME_FIXTURES.items():
    _fixture.update({
        'site_domain': 'localhost:18000',
        'namespace': 'py36-r2-e6-{}'.format(_runtime),
    })
R1.EXPECTED_ORA2_COMMIT = os.environ['PY36_R2_E6_EXPECTED_ORA2_COMMIT']
# The R2 source includes Platform #2369 (owner-accepted contract delta).
R1.PENDING_COURSE_PROGRESS_ROWS = 0

from django.conf import settings  # noqa: E402
from django.contrib.sites.models import Site  # noqa: E402
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration  # noqa: E402
from openedx.core.djangoapps.theming.models import SiteTheme  # noqa: E402

settings.ORA2_GATE_QUEUES = dict(settings.GRADING_QUEUES)


def _host_platform_identity():
    return {
        'source_root': settings.REPO_ROOT,
        'commit': os.environ['PY36_R2_E6_PLATFORM_COMMIT'],
        'tree': os.environ['PY36_R2_E6_PLATFORM_TREE'],
        'verified_by': 'host git (run-r2-e6-services.sh start)',
    }


def _ensure_canonical_site(fixture):
    site = Site.objects.get(domain=fixture['site_domain'])
    config = SiteConfiguration.objects.get(site=site)
    values = dict(config.values or {})
    previous = {key: values.get(key) for key in ('course_org_filter', 'ENABLE_LAST_ACTIVITY')}
    values.update({'course_org_filter': fixture['course_key_object'].org, 'ENABLE_LAST_ACTIVITY': True})
    config.enabled = True
    config.values = values
    config.save()
    themes = SiteTheme.objects.filter(site=site)
    removed = sorted(themes.values_list('theme_dir_name', flat=True))
    themes.delete()
    if SiteTheme.objects.filter(site=site).exists():
        raise RuntimeError('site theme is still set for {}'.format(site.domain))
    print('E6_ORA2_SITE site_id={} domain={} previous={} unthemed={}'.format(
        site.id, site.domain, sorted(previous.items()), removed,
    ))
    return site


# R1's gate settings defined ORA2_ASSESSMENTS with a staff entry; the Platform
# sets neither it nor ORA2_ASSESSMENT_SCORE_PRIORITY, so ORA2 adds the staff
# step to AssessmentWorkflow when the first workflow is instantiated, as in
# every LMS request that loads one. Record the class state before that.
def _platform_settings_identity(fixture):
    from openassessment.workflow.models import AssessmentWorkflow

    before = {'steps': list(AssessmentWorkflow.STEPS),
              'score_priority': list(AssessmentWorkflow.ASSESSMENT_SCORE_PRIORITY)}
    AssessmentWorkflow()
    R1._emit('IDENTITY_OK', {
        'runtime': fixture['runtime'],
        'namespace': fixture['namespace'],
        'platform': R1._platform_identity(),
        'packages': R1._source_identity(),
        'workflow_class_before_first_instance': before,
        'workflow_score_priority': AssessmentWorkflow.ASSESSMENT_SCORE_PRIORITY,
        'settings': {
            'celery_always_eager': settings.CELERY_ALWAYS_EAGER,
            'celery_task_always_eager': settings.CELERY_TASK_ALWAYS_EAGER,
            'ora2_assessments': getattr(settings, 'ORA2_ASSESSMENTS', 'unset (ORA2 default)'),
            'ora2_score_priority': getattr(settings, 'ORA2_ASSESSMENT_SCORE_PRIORITY', 'unset (ORA2 default)'),
            'ora2_fileupload_backend': settings.ORA2_FILEUPLOAD_BACKEND,
            'grade_routing_key': settings.RECALCULATE_GRADES_ROUTING_KEY,
            'progress_routing_key': settings.RECALCULATE_PROGRESS_ROUTING_KEY,
        },
    })


R1._platform_identity = _host_platform_identity
R1._ensure_site = _ensure_canonical_site
R1.identity = _platform_settings_identity

if __name__ == '__main__':
    R1.main()
