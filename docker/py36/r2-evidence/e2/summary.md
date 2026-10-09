# E2 runtime image summary - 2026-10-09 18:03:23 +0800
image ltdps/edxapp:py36-r2-20261009 sha256:4560a9c2b264ba25f5cf93bd49ee7e163eb2133e24d537811dbaf45c84d397ce arm64 linux created=2026-10-09T17:56:26.834888846+08:00
devstack lock commit bd52bec (net vs 09c7da2: -5 enterprise-family pins x 2 files)
platform build context: platform-r2-py36-src @ fd5e359ec1c (tree 5d7e28bb7bbc)
build: no-cache, exit 0, 17:42:03-17:56:43; DEBIAN_SECURITY_MIRROR=http://archive.debian.org/debian-security (attempt1-tuna-security-404/diagnosis.txt)

| Check | Result |
|---|---|
| Dockerfile smoke | 2x 'Image build OK', 2x 'XModule entry points OK' |
| pip check | No broken requirements found. |
| freeze | 221 lines, sha256 cd1a0ac1aa3bfe0658299b8e3bc5f4064117fb030c7f62e71c9c876494bfe33f; vs R1 226-line baseline: -5 (edx-enterprise, django-multi-email-field, django-object-actions, djangorestframework-xml, jsondiff), ORA2 0d89f917 -> d3f24a9c; nothing else |
| xmodule.v1 | 35 entry points, 0 load failures, course=CourseDescriptor, hidden=HiddenDescriptor (LMS and CMS, probe settings) |
| openedx.course_tool | course_bookmarks, course_reviews, course_updates; verified_upgrade absent |
| site-packages compile | exit 1, exactly 3 accepted paths, path-set sha256 cc0d80d80af5265818ab93252ca953396a5c7a899ff375f1e0b7e2eb7b19b630 (= R1) |

Finding (carry to E3): plain lms|cms.envs.test cannot django.setup() - duplicate edx_proctoring label; reproduces with R1 source; see finding-edx-proctoring-duplicate.txt
