"""Real course, users and authorization; temporary MySQL rows roll back."""
import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.test import RequestFactory
from opaque_keys.edx.keys import CourseKey

from contentstore.views.component import component_handler
from student.auth import has_course_author_access
from student.models import UserProfile
from student.roles import CourseStaffRole, STUDIO_ADMIN_ACCESS_GROUP
from xmodule.modulestore.django import modulestore

course = CourseKey.from_string('course-v1:PY313+RuntimeChrome26+2026')
block = next(item for item in modulestore().get_items(course) if item.category == 'scormxblock')
factory = RequestFactory(HTTP_HOST='localhost:18010')
with transaction.atomic():
    suffix = secrets.token_hex(5)
    def user(name, editor=False):
        value = get_user_model().objects.create_user(name + suffix)
        UserProfile.objects.create(user=value, name='Permission acceptance')
        if editor:
            value.groups.add(Group.objects.get_or_create(name=STUDIO_ADMIN_ACCESS_GROUP)[0])
        return value

    learner = user('learner_')
    outsider = user('other_course_editor_', True)
    author = user('course_author_', True)
    CourseStaffRole(course).add_users(author)
    assert has_course_author_access(author, course)
    assert not has_course_author_access(outsider, course)
    for identity, expected in [(AnonymousUser(), 302), (learner, 403), (outsider, 403), (author, 404)]:
        for method in ['get', 'post']:
            request = getattr(factory, method)('/xblock/permission-acceptance')
            request.user = identity
            try:
                response = component_handler(request, str(block.location), 'missing_acceptance_handler')
                actual = response.status_code
            except PermissionDenied:
                actual = 403
            except Http404:
                actual = 404
            assert actual == expected, (identity.is_anonymous, method, actual, expected)
        print('PASS handler boundary:', 'anonymous' if identity.is_anonymous else identity.username.split(suffix)[0], expected)
    transaction.set_rollback(True)
print('PASS real SCORM component permission boundary; no handler or content mutation')
