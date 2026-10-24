"""Verify the LMS and CMS course-list search callers forward ``search_term``."""
from unittest.mock import patch

import django
from django.conf import settings
from django.test import RequestFactory
import search.api

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from cms.djangoapps.contentstore.api.views.courses_query import UserCourseListView  # noqa: E402
from lms.djangoapps.course_api.views import CourseListView  # noqa: E402


def main():
    user = get_user_model().objects.filter(is_active=True).first()
    if user is None:
        raise AssertionError("acceptance database has no active user")
    factory = RequestFactory()
    calls = []

    def search(**kwargs):
        calls.append(kwargs)
        return {"results": []}

    with patch("cms.djangoapps.contentstore.api.views.courses_query.get_visible_courses", return_value=[]), \
            patch("cms.djangoapps.contentstore.api.views.courses_query.search.api.course_discovery_search", side_effect=search):
        cms_view = UserCourseListView()
        cms_view.request = factory.get("/api/courses/?search_term=Python", data={"search_term": "Python"})
        cms_view.request.user = user
        cms_view.request.query_params = cms_view.request.GET
        cms_view.get_queryset()

    with patch("lms.djangoapps.course_api.views.list_courses", return_value=[]), \
            patch("lms.djangoapps.course_api.views.search.api.course_discovery_search", side_effect=search), \
            patch.dict(settings.FEATURES, {"ENABLE_COURSEWARE_SEARCH": True}):
        lms_view = CourseListView()
        lms_view.request = factory.get("/api/courses/?search_term=Python", data={"search_term": "Python"})
        lms_view.request.user = user
        lms_view.request.query_params = lms_view.request.GET
        lms_view.get_queryset()

    assert len(calls) == 2, calls
    assert all(call["search_terms"] == {"Python"} for call in calls), calls
    print("cms and lms search callers forwarded search_terms={'Python'}")


if __name__ == "__main__":
    main()
