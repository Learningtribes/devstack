# Piped into `run-r2-e4-services.sh shell lms|cms`. manage.py shell execs this
# inside a function, so only locals are used.
import sys
from collections import Counter

from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore

store = modulestore()
courses = list(store.get_courses())
print('COURSES count=%d python=%s' % (len(courses), sys.version.split()[0]))
for c in sorted(courses, key=lambda c: str(c.id)):
    print('COURSES id=%s' % c.id)
course = store.get_course(CourseKey.from_string('course-v1:QA+Acceptance+Test'), depth=None)
types = Counter()
stack = [course]
while stack:
    block = stack.pop()
    types[block.category] += 1
    stack.extend(block.get_children())
print('COURSE_READ id=%s name=%r blocks=%d' % (course.id, course.display_name, sum(types.values())))
print('COURSE_TYPES %s' % sorted(types.items()))
print('E4_COURSE_OK')
