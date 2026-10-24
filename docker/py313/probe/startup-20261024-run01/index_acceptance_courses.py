"""Populate discovery using actual retained course content, without deleting indexes."""
import logging
import django

django.setup()
from django.conf import settings
from cms.djangoapps.contentstore.courseware_index import CourseAboutSearchIndexer
from opaque_keys.edx.keys import CourseKey
from search.elastic import ElasticSearchEngine
from xmodule.modulestore.django import modulestore

failures = []
class StrictIndexLog(logging.Handler):
    def emit(self, record):
        if record.levelno >= logging.WARNING and ('could not collect' in record.getMessage() or record.exc_info):
            failures.append(record.getMessage())
handler = StrictIndexLog()
logger = logging.getLogger('edx.modulestore')
logger.addHandler(handler)
keys = ['course-v1:PY313+RuntimeChrome26+2026', 'course-v1:PY313+DiscussionRun03+2026']
try:
    assert CourseAboutSearchIndexer.INDEX_NAME == settings.COURSEWARE_INDEX_NAME
    for key in keys:
        store = modulestore()
        course = store.get_course(CourseKey.from_string(key))
        CourseAboutSearchIndexer.index_about_information(store, course)
    engine = ElasticSearchEngine(settings.COURSEWARE_INDEX_NAME)
    engine._es.indices.refresh(index=engine._prefixed_index_name)
    result = engine.search(doc_type='course_info',query_strings=['Python'],size=20)
    ids = [r['data']['id'] for r in result['results']]
    print('producer_consumer_index',engine._prefixed_index_name,'course_ids',ids)
    assert set(keys).issubset(ids)
    assert not failures, failures
finally:
    logger.removeHandler(handler)
print('PASS actual ModuleStore course metadata indexed without swallowed collection errors')
