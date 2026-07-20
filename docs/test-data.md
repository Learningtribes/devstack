# Test Data Setup Guide

> Date: 2026-07-19

## Test Users

All passwords: `edx`

| Username | Superuser | Staff | Role |
|----------|:---------:|:-----:|------|
| `edx` | ✅ | ✅ | Super admin |
| `studio_admin` | ✅ | ✅ | Studio admin |
| `staff` | ❌ | ✅ | Course staff |
| `instructor` | ❌ | ✅ | Course instructor |
| `learning_path_admin` | ❌ | ✅ | Learning Path admin |
| `honor` | ❌ | ❌ | Honor student |
| `audit` | ❌ | ❌ | Audit student |
| `verified` | ❌ | ❌ | Verified student |
| `learner1` | ❌ | ❌ | Regular learner |
| `learner2` | ❌ | ❌ | Regular learner |

### Create additional users

```bash
docker exec edx.devstack.lms bash -c '
source /edx/app/edxapp/edxapp_env && cd /edx/app/edxapp/edx-platform
python manage.py lms --settings=devstack_docker manage_user <username> <email> [--staff] [--superuser]
echo "from django.contrib.auth import get_user_model; u=get_user_model().objects.get(username=\"<username>\"); u.set_password(\"edx\"); u.save()" | python manage.py lms shell --settings=devstack_docker
'
```

## Test Courses

### Via Playwright Automation (recommended)

```bash
cd devstack
python3 scripts/create_test_courses.py           # headless
python3 scripts/create_test_courses.py --headed   # show browser
python3 scripts/create_test_courses.py --dry-run  # login only
```

Creates 5 courses with different component types using system Chrome. Prerequisites: `pip3 install playwright`.

### Via Studio UI

1. Login as `studio_admin` or `edx` at http://0.0.0.0:18010/
2. Click "New Course"
3. Fill in course details (org, number, name)
4. Add sections and units with different XBlock components

### Available XBlock types (38 installed)

See `xblock-inventory.md` for the full list.

### Quick course creation via command line

```bash
docker exec edx.devstack.lms bash -c '
source /edx/app/edxapp/edxapp_env && cd /edx/app/edxapp/edx-platform
# Create a course (minimal, no content)
python manage.py cms --settings=devstack_docker generate_course <org> <number> <run> --user edx
'
```

## Container Backup After Changes

```bash
docker commit edx.devstack.lms    ltdps/edxapp:m5-fixed
docker commit edx.devstack.studio ltdps/edxapp:m5-fixed-studio
```

## MySQL Backup After Changes

```bash
mkdir -p ~/workspace/hawthorn/backups/$(date +%Y%m%d)
docker exec edx.devstack.mysql mysqldump -uroot --databases edxapp edxapp_csmh | gzip > ~/workspace/hawthorn/backups/$(date +%Y%m%d)/mysql_edxapp.sql.gz
```
