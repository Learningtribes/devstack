"""Identifiers of the explicit isolated replay, never an old run's content."""
import os
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore


def course_key():
    return CourseKey.from_string(os.environ['PY313_ACCEPTANCE_COURSE_ID'])


def block_key(category):
    blocks = [item.location for item in modulestore().get_items(course_key()) if item.category == category]
    assert len(blocks) == 1, (category, len(blocks))
    return blocks[0]
