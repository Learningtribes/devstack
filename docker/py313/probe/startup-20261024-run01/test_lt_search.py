"""Real isolated Elasticsearch contract probes; no platform acceptance claimed."""
from datetime import datetime, timedelta
import uuid
import unittest
from django.conf import settings
RUN = 'py313_probe_' + uuid.uuid4().hex
settings.configure(SECRET_KEY='ephemeral-unit-only', INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','waffle'],
    DATABASES={'default': {'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}},
    CACHES={'default': {'BACKEND':'django.core.cache.backends.locmem.LocMemCache'}},
    SEARCH_ENGINE='search.elastic.ElasticSearchEngine', ELASTIC_SEARCH_CONFIG=[{'host':'py313.elasticsearch','port':9200}],
    ELASTIC_SEARCH_INDEX_PREFIX=RUN+'_', COURSEWARE_INDEX_NAME='courses', PROGRAM_INDEX_NAME='programs',
    SEARCH_SKIP_ENROLLMENT_START_DATE_FILTERING=True, COURSE_DISCOVERY_FILTERS=['languages'],
    PROGRAM_DISCOVERY_FILTERS=['languages'])
import django
django.setup()
from django.core.management import call_command
call_command('migrate', verbosity=0)
from search.elastic import ElasticSearchEngine
from search import api
from search.utils import DateRange
print('Dedicated resource prefix:', RUN, flush=True)

class LTSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=ElasticSearchEngine('courses')
        cls.programs=ElasticSearchEngine('programs')
        future=(datetime.now()+timedelta(days=20)).isoformat()
        past=(datetime.now()-timedelta(days=20)).isoformat()
        def document(id_, org='one', **kw):
            return dict(id=id_, course=id_, org=org, raw_display_name=id_, start=past,
                end=future, languages=['en'], course_status='released', content={'display_name':'Ocean Safety '+id_}, **kw)
        cls.engine.index('course_info',[
            document('Alpha'), document('Beta',discoverable_only_by_targeted=True),
            document('Gamma',org='two'), {**document('Old'),'end':past},
            document('Private', discoverable_only_by_targeted=True),
        ],refresh=True)
        cls.engine.index('courseware_content',[dict(id='Alpha',course='Alpha',org='one',content={'display_name':'Ocean body'})],refresh=True)
        cls.programs.index('program', [dict(id='LP',uuid='LP',raw_title='Ocean',start=past,languages=['en'],
            org='one',course_status='released',content={'title':'Ocean Safety'})],refresh=True)
    def test_real_index_targeting_permissions_and_counts(self):
        result=self.engine.search(query_strings=['Ocean','Safety'],doc_type='course_info',
            field_dictionary={'org':['one'],'course':['Alpha','Beta','Old','Private']},
            filter_dictionary={'end': {'value':DateRange(datetime.now(),None),'missing_included':True}},
            targeting_gate={'flag_field':'discoverable_only_by_targeted','key_field':'course','allowed':['Beta']},
            facet_terms={'languages':{}},sort=[{'raw_display_name':'asc'}],ga_total=True)
        self.assertEqual([r['data']['id'] for r in result['results']],['Alpha','Beta'])
        self.assertEqual(result['facets']['languages']['terms'],{'en':2})
        self.assertEqual(result['doc_count'],3)  # authorized catalog before date filters
        self.assertEqual(result['facets']['languages']['missing'],0)
        missing=self.engine.search(doc_type='courseware_content', facet_terms={'languages':{}})
        self.assertEqual(missing['facets']['languages']['missing'],1)
        denied=self.engine.search(doc_type='course_info',field_dictionary={'course':[]})
        self.assertEqual(denied['total'],0)
    def test_api_three_caller_signatures_and_programs(self):
        for _ in range(2):
            result=api.course_discovery_search(search_terms={'Ocean'},size=20)
            self.assertEqual(result['total'],5)
        result=api.course_discovery_search(search_terms={'Ocean'},size=20,from_=0,
            field_dictionary={'org':['one'],'course':['Alpha']},exclude_languages=[],
            exclude_course_category=[],exclude_course_type=[],exclude_privilege_ids=[],exclude_course_country=[],
            exclude_enrollment_learning_groups=[],user=None,include_course_filter=True,only_released_courses=False,
            archived=False,sort_type='+display_name',ga_total=True)
        self.assertEqual([r['data']['id'] for r in result['results']],['Alpha'])
        programs=api.programs_discovery_search(search_terms={'Ocean'},field_dictionary={'org':['one']})
        self.assertEqual([r['data']['id'] for r in programs['results']],['LP'])
    def test_types_exclusions_and_removal(self):
        result=self.engine.search(doc_type='course_info',field_dictionary={'org':['one']},exclude_dictionary={'course':['Beta','Old','Private']})
        self.assertEqual([r['_id'] for r in result['results']],['Alpha'])
        self.engine.remove('courseware_content',['Alpha'],refresh=True)
        self.assertEqual(self.engine.search(doc_type='course_info',field_dictionary={'id':'Alpha'})['total'],1)
        self.assertEqual(self.engine.search(doc_type='courseware_content')['total'],0)
if __name__=='__main__': unittest.main(verbosity=2)
