#!/bin/bash
# Enable all advanced XBlock modules for existing courses
# Usage: bash scripts/enable_advanced_modules.sh

docker exec edx.devstack.lms bash -c 'source /edx/app/edxapp/edxapp_env && cd /edx/app/edxapp/edx-platform && python manage.py cms shell --settings=devstack_docker' <<'PYEOF'
from xmodule.modulestore.django import modulestore
store = modulestore()

advanced = [
    "drag-and-drop-v2", "externality", "icxblock", "iframe", "ilt",
    "lbmdonexblock", "openassessment", "pdf", "poll", "scormxblock",
    "survey", "videoalpha", "word_cloud", "library_content",
    "google-document", "google-calendar", "done", "acid", "acid_parent",
    "recommender", "lti_consumer", "edx_sga", "ubcpi",
    "audio", "animation", "activetable", "concept", "vectordraw",
    "officemix", "oppia", "rate", "problem-builder", "crowdsourcehinter",
    "review", "schoolyourself_lesson", "schoolyourself_review",
]

for course in store.get_courses():
    if hasattr(course, "advanced_modules"):
        course.advanced_modules = advanced
        store.update_item(course, "studio_admin")
        print("Updated: %s" % course.id)
print("Done")
PYEOF
