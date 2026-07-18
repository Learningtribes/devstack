# Hawthorn Devstack — Mac M5 + OrbStack Setup Complete Guide

> Apple Silicon (M5) + OrbStack 2.2.1 + macOS Tahoe 26.5.1  
> Date: 2026-07-18  
> Result: ✅ LMS (18000) + Studio (18010) all services running

---

## 1. Prerequisites

### Environment

| Item | Value |
|------|-------|
| Local path | `/Users/noahwang/workspace/hawthorn/devstack` |
| Remote reference | `pcupgrade_nat` (VMware on Win11, internal network) |
| Login credentials | `edx` / `edx` |

**Required environment variables** (add to `~/.zshrc` or `~/.bashrc`):

```bash
export DEVSTACK_WORKSPACE=/Users/noahwang/workspace/hawthorn
```

- `DEVSTACK_WORKSPACE` — required for bind mounts in docker-compose-host.yml

**Note:** This branch (`apple-m-chip`) has docker-compose.yml modified for M-series Macs. The original x86 version lives on `master`.

### Installed Tools

- OrbStack 2.2.1 (replaces Docker Desktop)
- Rosetta emulation enabled (`orb config get rosetta` → true)

### Image List

| Image | Size | Arch |
|------|------|------|
| mysql:5.6 | 423MB | x86 |
| mongo:3.2.16 | 424MB | x86 |
| memcached:1.5.4 | 95MB | x86 |
| edxops/elasticsearch:devstack | 530MB | x86 |
| ltdps/devpi:latest | 1.6GB | x86 |
| ltdps/edxapp:latest | 4.0GB | x86 |
| ltdps/forum:latest | 2.0GB | x86 |
| ltdps/discovery:latest | 2.8GB | x86 |
| ltdps/ecommerce:latest | 2.9GB | x86 |

---

## 2. Issues and Solutions

### 1. Image Architecture Incompatibility

**Problem:** `docker compose pull` error `no matching manifest for linux/arm64/v8`

**Cause:** All devstack images are x86 only, no ARM64 variants.

**Fix:** Add `platform: linux/amd64` to every service in docker-compose.yml.

```yaml
services:
  mysql:
    image: mysql:5.6
    platform: linux/amd64
```

### 2. memcached manifest v1 Incompatibility

**Problem:** `memcached:1.4.24` uses Docker manifest v1 format, unsupported by OrbStack containerd v2.1.

**Fix:** Upgrade to `memcached:1.5.4` (uses manifest v2). No compatibility impact as a pure cache.

### 3. Docker Hub Pull Speed

**Problem:** Docker registry mirrors (1ms.run, xuanyuan.me, daocloud.io) throttle old large images severely (~10KB/s).

**Fix:** Temporarily clear mirrors in `~/.orbstack/config/docker.json` for direct Docker Hub access. Restore after pulling.

```bash
echo '{"registry-mirrors": []}' > ~/.orbstack/config/docker.json
orb restart docker
```

**Note:** Switching Clash proxy nodes does not affect existing TCP connections. Kill processes and reconnect.

### 4. DEVSTACK_WORKSPACE Not Set

**Problem:** Container mount `/edx/app/edxapp/edx-platform` shows only `node_modules` volume, no source files.

**Fix:** Always set `DEVSTACK_WORKSPACE` before docker compose commands.

```bash
export DEVSTACK_WORKSPACE=/Users/noahwang/workspace/hawthorn
DEVSTACK_WORKSPACE=$DEVSTACK_WORKSPACE docker compose -f docker-compose.yml -f docker-compose-host.yml up -d lms studio
```

### 5. Node.js Too Old (v8.9.3 → v16.20.2)

**Problem:** Container ships with Node v8.9.3, but edx-platform `node-sass: ^8` requires Node 14+.

**Fix:** Download Node 16.20.2 binary on host, inject via bind mount into the container's nodeenv.

```bash
# Host
curl -sL https://nodejs.org/dist/v16.20.2/node-v16.20.2-linux-x64.tar.gz -o /tmp/n16.tar.gz
cp /tmp/n16.tar.gz $DEVSTACK_WORKSPACE/platform/

# Container
source /edx/app/edxapp/edxapp_env
rm -rf /edx/app/edxapp/nodeenvs/edxapp
mkdir -p /edx/app/edxapp/nodeenvs/edxapp
tar xzf /edx/app/edxapp/edx-platform/n16.tar.gz --strip-components=1 -C /edx/app/edxapp/nodeenvs/edxapp
```

### 6. Corrupted node_modules After Failed npm Install

**Problem:** Multiple failed npm installs leave corrupted files in the shared volume (`ENOTEMPTY`).

**Fix:** Clean both Docker volume and host directory, then recreate containers.

```bash
docker rm -f edx.devstack.lms edx.devstack.studio
docker volume rm devstack_edxapp_node_modules
rm -rf $DEVSTACK_WORKSPACE/platform/node_modules
```

### 7. No Container Network Access

**Problem:** Containers cannot reach external network (apt-get, nodeenv download all timeout).

**Cause:** OrbStack containers route through host proxy (Clash Party), which is unstable.

**Workaround pattern:** Download on host → inject via bind mount:
- Node binary → host curl
- .deb packages → host curl from Ubuntu archive
- pip packages → devpi cache + remote sync

### 8. python-ldap Missing + Missing Build Chain

**Problem:** `ImportError: No module named ldap`. The ltdps/edxapp image venv lacks python-ldap and django-auth-ldap.

**Fix:**
1. Host downloads libldap2-dev, libsasl2-dev, etc. .deb packages
2. Inject into container via bind mount, `dpkg -i`
3. `pip install python-ldap==2.4.44 django-auth-ldap==1.2.15`

### 9. pysaml2 + xmlsec1 Missing

**Problem:** After ldap fixed, `ImportError: No module named saml2`, then `SigverError: Cannot find xmlsec1`.

**Fix:** pip install pysaml2==4.9.0 (wheel available in devpi), download xmlsec1 .deb from host.

### 10. django-tables2 Python 2 Compatibility

**Problem:** Latest django-tables2 3.0.0 has SyntaxError on Python 2.7 (non-ASCII char).

**Fix:** Install matching remote version `django-tables2==1.16.0`.

### 11. drf-nested-routers Python Version Requirement

**Problem:** Latest version requires Python >= 3.8.

**Fix:** Install legacy version `drf-nested-routers==0.91`.

### 12. ImportError Cascade (Core Strategy: Sync site-packages from Remote)

**Problem:** Fixing packages one by one hits cascading ImportErrors, and pip downloads are slow.

**Fix:** Export complete site-packages + venv/src from the remote devstack and overwrite locally.

```bash
# Remote export
ssh -J home_zyw pcupgrade_nat 'docker cp edx.devstack.lms:/edx/app/edxapp/venvs/edxapp/lib/python2.7/site-packages /tmp/remote_sp; cd /tmp && tar czf sp.tar.gz remote_sp'
scp -o ProxyJump=home_zyw pcupgrade_nat:/tmp/sp.tar.gz /tmp/
# Same for venv/src

# Local: extract and replace site-packages. Then pip install -e for each src package.
```

### 13. cffi/cryptography Shared Library Mismatch

**Problem:** After copying remote site-packages, cryptography errors with `libffi-xxx.so.6.0.4: cannot open shared object file`. Remote cffi was compiled against a different libffi version.

**Fix:** Reinstall cffi and cryptography from source locally:

```bash
pip uninstall -y cffi cryptography
# Install libffi-dev first (download .deb and inject)
dpkg -i libffi-dev*.deb
pip install cffi==1.11.5 cryptography==2.2.2
```

**Critical:** Must specify exact versions, or pip pulls latest (Python 2 incompatible). Must compile from source (not wheel), as wheel links to different libffi.

### 14. edx-search Not Registered as Python Package

**Problem:** `No module named search.search_engine_base`. Files exist at `/edx/app/edxapp/edx-search/` but not installed.

**Fix:** `pip install -e /edx/app/edxapp/edx-search`

### 15. edx_proctoring and Local Packages Missing

**Problem:** After copying remote site-packages, .egg-link files point to wrong paths.

**Fix:** Export remote `venvs/edxapp/src/` to local, then `pip install -e` each package.

### 16. Login Page 500 — Database Not Migrated

**Problem:** LMS and Studio return 500 on /login after startup.

**Fix:** Run migrations:

```bash
docker exec edx.devstack.lms bash -c '
source /edx/app/edxapp/edxapp_env
cd /edx/app/edxapp/edx-platform
paver update_db --settings devstack_docker
'
```

### 17. Ansible demo course Hangs

**Problem:** provision script's ansible-playbook tries apt-get install, hangs due to no container network.

**Fix:** Skip demo course (not required).

### 18. Studio webpack-stats.json

**Problem:** Studio's webpack step calls `manage.py lms` which fails in Studio container.

**Correct approach:** LMS and Studio compile independently:
```bash
# LMS container
paver update_assets lms --settings=devstack_docker

# Studio container (in make studio-shell)
paver update_assets cms --settings=devstack_docker
```

If Studio webpack fails due to network, run step-by-step:
```bash
paver compile_sass --system=cms --settings=devstack_docker
paver webpack
python manage.py cms --settings=devstack_docker collectstatic ...
```

### 19. LMS Dashboard 缺 enrollment_date 列

**问题:** `Unknown column 'student_courseenrollment.enrollment_date'`

**解决:** 远程 devstack 数据库有额外列，本地 dump 缺失：
```sql
ALTER TABLE student_courseenrollment ADD COLUMN enrollment_date datetime(6) NULL;
ALTER TABLE student_courseenrollment ADD COLUMN origin varchar(50) NULL;
ALTER TABLE student_courseenrollment ADD COLUMN history longtext NOT NULL;
ALTER TABLE student_courseenrollment ADD COLUMN to_recompile tinyint(1) NOT NULL DEFAULT 0;
ALTER TABLE student_courseenrollment CHANGE COLUMN completed completion_date datetime(6) NULL;
```

### 19a. 缺 course_status 列（影响课程显示）

**问题:** `course_overviews_courseoverview.course_status` 列不存在，导致 `generate_course_overview` 失败。

**解决:**
```sql
ALTER TABLE course_overviews_courseoverview ADD COLUMN course_status varchar(50) NULL;
```

### 19b. ES 索引 mapping 不完整（课程列表不显示）

**问题:** Studio 课程列表页完全空白（不仅新建课程，手动创建的也不显示）。ES 索引 `courseware_index` 本地从零建立时 mapping 缺少 `raw_display_name`、`course_type`、`course_category` 等字段及 `partword`/`case_insensitive_sort` 自定义 analyzer，导致搜索排序失败返回空结果。

**根因:** 本地 ES 数据卷是新创建的，mapping 不完整；远程 devstack 的 ES 是长期运行积累的完整 mapping。

**解决（远程在线时）：**
1. 从远程导出完整 index settings + mapping
2. 删除本地索引，按远程 settings + mapping 重建
3. 重新索引所有课程

```bash
# 从远程导出 mapping
ssh -J home_zyw pcupgrade_nat "curl -s 'http://localhost:9200/courseware_index/_settings'" > /tmp/es_settings.json
ssh -J home_zyw pcupgrade_nat "curl -s 'http://localhost:9200/courseware_index/_mapping'" > /tmp/es_mapping.json

# 合并为 create body 并重建本地索引
python3 -c "
import json
s=json.load(open('/tmp/es_settings.json'))['courseware_index']['settings']['index']
m=json.load(open('/tmp/es_mapping.json'))['courseware_index']['mappings']
json.dump({'settings':{'index':s},'mappings':m}, open('/tmp/es_create.json','w'))
"
curl -s -XDELETE 'http://localhost:9200/courseware_index'
curl -s -XPUT 'http://localhost:9200/courseware_index' -d @/tmp/es_create.json

# 重新索引
docker exec edx.devstack.lms bash -c 'source /edx/app/edxapp/edxapp_env && cd /edx/app/edxapp/edx-platform && python manage.py cms shell --settings=devstack_docker <<EOF
from contentstore.courseware_index import CourseAboutSearchIndexer, CoursewareSearchIndexer
from xmodule.modulestore.django import modulestore
store = modulestore()
for course in store.get_courses():
    CourseAboutSearchIndexer.index_about_information(store, course)
    CoursewareSearchIndexer.index(store, course.id)
    print("Indexed: " + str(course.id))
print("Done")
EOF'
```

**是否会复现：** 只要 ES 数据卷 (`devstack_elasticsearch_data`) 不被删除，新建课程会自动索引。`docker compose down -v` 会清除所有数据卷，恢复后需重新执行上述修复并 restore MySQL dump。

### 19c. program_index ES mapping 缺失（Programs tab 不显示）

**问题:** `/program_search/` 返回 500，Programs tab 空白。根因与 19b 相同：本地 ES 从零创建时，`program_index` 缺少远程运行的完整 mapping（settings 中的 `partword`/`case_insensitive_sort` 自定义 analyzer，以及 `raw_title`、`start`、`course_status`、`creator_id`、`created`、`modified` 等字段）。

**前端报错:** `Invalid time value` at `date_utils.js:133` → 缺 `created` 字段；`KeyError: 'creator_id'` → 缺 `creator_id` 字段。

**解决:**
1. 从 remote 或 courseware_index 获取 settings（含 analyzer 定义）
2. 创建 index 并应用 mapping
3. 索引 programs（补全所有必需字段）

```bash
# 1. Create index with analyzers from courseware_index
curl -s 'http://localhost:9200/courseware_index/_settings' | python3 -c "
import sys,json
s=json.load(sys.stdin)['courseware_index']['settings']
json.dump({'settings':s}, open('/tmp/ps.json','w'))
"
curl -s -XDELETE 'http://localhost:9200/program_index'
curl -s -XPUT 'http://localhost:9200/program_index' -d @/tmp/ps.json

# 2. Apply mapping (title with raw_title, start, end, course_status, etc.)
curl -s -XPUT 'http://localhost:9200/program_index/programs/_mapping' -d '{
  "properties": {
    "title": {"type":"string","analyzer":"partword","fields":{"raw_title":{"type":"string","analyzer":"case_insensitive_sort"}}},
    "start": {"type":"date","format":"dateOptionalTime"},
    "end": {"type":"date","format":"dateOptionalTime"},
    "org": {"type":"string","index":"not_analyzed"},
    "status": {"type":"string","index":"not_analyzed"},
    "visibility": {"type":"string","index":"not_analyzed"},
    "course_status": {"type":"string","index":"not_analyzed"}
  }
}'

# 3. Re-index from discovery DB
docker exec edx.devstack.lms bash -c 'source /edx/app/edxapp/edxapp_env && cd /edx/app/edxapp/edx-platform && python manage.py cms shell --settings=devstack_docker' <<EOF
import MySQLdb; from datetime import datetime
from search.search_engine_base import SearchEngine
conn = MySQLdb.connect(host="edx.devstack.mysql", user="root", db="discovery", charset="utf8")
cur = conn.cursor()
cur.execute("SELECT id,title,uuid,status,creator_id,created,modified FROM course_metadata_program")
searcher = SearchEngine.get_search_engine("program_index")
now = datetime.utcnow().isoformat()
for r in cur.fetchall():
    pid, title, uuid, status, creator_id, created, modified = r
    searcher.index("programs", [{
        "id":str(pid),"title":title,"org":"edX","status":status or "active",
        "uuid":str(uuid or pid),"creator_id":creator_id or 2,
        "start":None,"end":None,"card_image_url":None,"courses_count":0,
        "visibility":"visible","vendor":None,"duration":"","languages":[],
        "released_date":None,"course_status":"released",
        "created":str(created) if created else now,
        "modified":str(modified) if modified else now,
    }])
print("Done")
EOF
```

**是否会复现：** 同 19b，ES 数据卷不丢则不会。丢失后需重新执行。三个 ES 索引（courseware/library/program）遵循相同修复模式。

### 19d. 缺失的自定义 MySQL 表

Learningtribes 分支有一些自定义表不在原始 provision dump 中，运行时触发 `Table doesn't exist`。

| Table | Impact | Fix |
|-------|--------|-----|
| `course_overviews_courserating` | LMS mixed 搜索 500 | CREATE TABLE |
| `course_programprivilegeflag` | LP 详情页 500 | CR...[truncated]

### 20. Studio Log Directory Missing

**Problem:** `No such file or directory: '/edx/var/log/lms/metrics_page_views_logger.csv'`

**Fix:**
```bash
docker exec edx.devstack.lms mkdir -p /edx/var/log/lms /edx/var/log/cms
docker exec edx.devstack.studio mkdir -p /edx/var/log/lms /edx/var/log/cms
```

### 21. Sites Domain Matching

**Problem:** Accessing via `localhost:18000` has no theme/config, but `0.0.0.0:18000` works fine.

**Cause:** Django Sites framework matches request Host header against `django_site.domain`.

**Fix:** Add localhost site entries with config and theme matching 0.0.0.0 entries.

### 22. Theme CSS Compilation

**Problem:** Theme not applied after enabling comprehensive theming.

**Correct workflow:**
1. `git pull` to ensure theme repo is up to date (CSS is tracked in git)
2. Update `lms.env.json` / `cms.env.json`:
   - `ENABLE_COMPREHENSIVE_THEMING: true`
   - `COMPREHENSIVE_THEME_DIRS: ["/edx/src/themes/"]`
3. MySQL inserts: `django_site` → `site_configuration_siteconfiguration` → `theming_sitetheme`
4. `paver update_assets lms --settings=devstack_docker` (compiles theme SCSS)
5. Restart containers

### 23. LMS Fixes Not Synced to Studio (Core Lesson)

**Problem:** LMS works after full repair, but Studio still throws various errors (xmlsec1 missing, node-sass binding incompatible, ldap ImportError, etc.). Root cause: most fixes were only applied to the LMS container. Studio is an independent container instance and needs **every fix applied separately**.

**Fixes that must be synced to Studio:**

| # | Fix | LMS | Studio | Action |
|---|-----|-----|--------|--------|
| 1 | Node 8 → 16 | ✅ | ❌→✅ | Extract n16.tar.gz into nodeenvs/edxapp |
| 2 | libldap2-dev + libsasl2-dev | ✅ | ❌→✅ | dpkg -i .deb |
| 3 | libffi-dev | ✅ | ❌→✅ | dpkg -i .deb |
| 4 | xmlsec1 | ✅ | ❌→✅ | dpkg -i .deb |
| 5 | site-packages replacement | ✅ | ❌ | Sync from remote (same source as LMS) |
| 6 | venv/src sync | ✅ | ❌ | Sync from remote |
| 7 | pip install -e src/* | ✅ | ✅ | Done during site-packages sync |
| 8 | cffi + cryptography recompile | ✅ | ✅ | Must redo in Studio container |
| 9 | edx-search pip install -e | ✅ | ❌→✅ | Bind mount active, verify egg-link |
| 10 | node-sass rebuild | ✅ | ❌→✅ | Required after Node upgrade |
| 11 | edx-platform setup.py develop | ✅ | ✅ | Bind mount active |
| 12 | paver update_assets | ✅ | ❌ | Sass + webpack + collectstatic |

**Key principle:** LMS and Studio share the same image but are independent containers. Any in-container modification (system packages, nodeenv, pip install) must be done **on both**. Only bind-mount shared directories (platform, themes, edx-search) are synchronized across both.

---

## 3. Final Status

### Running Services

| Service | Port | Status |
|---------|------|--------|
| MySQL | 3306 | ✅ |
| MongoDB | 27017 | ✅ |
| Elasticsearch | 9200 | ✅ |
| Memcached | 11211 | ✅ |
| Devpi | 3141 | ✅ |
| LMS | 18000 | ✅ |
| Studio | 18010 | ✅ |

### Verification

```bash
curl -o /dev/null -w "%{http_code}" http://localhost:18000/login   # 200
curl -o /dev/null -w "%{http_code}" http://localhost:18010/signin  # 200
curl -o /dev/null -w "%{http_code}" http://localhost:18010/        # 302
```

### Not Completed (Non-blocking)

- Demo course creation (ansible apt hangs, no container network)
- Other IDA services (discovery, ecommerce, forum) not started

### Completed ✅

- MySQL default config (auth groups, waffle switches, etc.)
- Translation file generation
- Sites config (LMS: 0.0.0.0:18000/localhost:18000, Studio: 0.0.0.0:18010/localhost:18010)
- Site Configuration (matching remote Triboo JSON)
- Site Theme (hawthorn) + comprehensive theming enabled

---

## 4. Standard Devstack → Manual Equivalent Mapping

`make dev.provision` is the standard one-click approach but fails completely on M5 + OrbStack. Here is the full manual equivalent:

| # | Standard Step | Manual Equivalent | Notes |
|---|--------------|-------------------|-------|
| 1 | `export OPENEDX_RELEASE=...` | Skip | Repos already in workspace |
| 2 | `virtualenv .venv && make requirements` | Skip | No host Python needed |
| 3 | `make dev.clone` | Skip | Repos already cloned |
| 4 | `make dev.provision` | See breakdown | All manual |
| 4a | └ `docker-compose up -d mysql mongo` | `docker compose -f docker-compose.yml up -d mysql mongo` | Same |
| 4b | └ `provision.sql + mongo-provision.js` | `docker exec -i ... mysql < provision.sql` + mongo | Same |
| 4c | └ `provision-lms.sh` | Manual steps (4c-1 ~ 4c-8) | See issues 5-16 |
| 4c-1 | └─ `load-db.sh` | Same, DB dumps available locally | ✅ |
| 4c-2 | └─ `docker-compose up lms studio` | `DEVSTACK_WORKSPACE=... docker compose -f ... -f ... up -d lms studio` | Must set DEVSTACK_WORKSPACE |
| 4c-3 | └─ `paver install_prereqs` | Manual: Upgrade Node 16 → npm install → pip install missing packages → sync remote site-packages | See issues 5-15 |
| 4c-4 | └─ `docker-compose restart lms` | `docker restart edx.devstack.lms` | Same |
| 4c-5 | └─ `paver update_db` | `docker exec ... paver update_db --settings devstack_docker` | ✅ Done |
| 4c-6 | └─ Create superuser | `docker exec ... manage_user edx ...` | ✅ edx/edx |
| 4c-7 | └─ ansible demo course | **Skip** (no container network) | ❌ |
| 4c-8 | └─ `paver update_assets` | `docker exec ... paver update_assets --settings devstack_docker` | ✅ Done in LMS |
| 5 | `make dev.up` | `docker compose ... up -d lms studio` | Same |
| 6 | `make lms-shell && apt-get install` | Host download .deb → bind mount → dpkg -i | No container network workaround |
| 7 | MySQL default config | `docker exec -i edx.devstack.mysql mysql -uroot edxapp < sql` | ✅ Done |
| 8 | Translation file generation | `docker exec ... python scripts/trans.py --all` | ✅ Done |

### Can Be Skipped

| Step | Reason |
|------|--------|
| `make dev.up.watchers` (asset watchers) | Not needed if not doing frontend dev |
| chrome/firefox containers | e2e tests only, commented out in compose |
| edx-notes-api / credentials / xqueue | Commented out in compose |
| forum / discovery / ecommerce | Not needed for core LMS/Studio dev |
| virtualenv / conda | Host doesn't need Python environment |

---

## 5. Completed Configuration (Executed 2026-07-18)

### 5.1 MySQL Default Config ✅

```bash
docker exec -i edx.devstack.mysql mysql -uroot edxapp <<'SQL'
insert into auth_group (name) values
  ('Studio Admin'), ('Learning Path Admin'), ('Catalog Denied Users'),
  ('EdFlex Denied Users'), ('Crehana Denied Users'), ('Anderspink Denied Users'),
  ('Restricted Triboo Analytics Admin'), ('Triboo Analytics Admin'),
  ('Multi-Sites Login'), ('Learnlight Denied Users'), ('Linkedin Learning Denied Users'),
  ('Udemy Denied Users'), ('Founderz Denied Users');
insert into waffle_switch (name, active, created, modified, note)
  values ('completion.enable_completion_tracking', 1, now(), now(), '');
insert into grades_persistentgradesenabledflag (enabled, enabled_for_all_courses, change_date)
  values (1, 1, now());
insert into bulk_email_bulkemailflag (enabled, require_course_email_auth, change_date)
  values (1, 0, now());
insert into certificates_certificategenerationconfiguration (enabled, change_date)
  values (1, now());
insert into dark_lang_darklangconfig (enabled, released_languages, change_date)
  values (1, 'ar, de-de, el, es-419, fr, it-it, pt-br, tr-tr, zh-cn', now());
SQL
```

### 5.2 Translation Files ✅

```bash
docker exec edx.devstack.lms bash -c '
source /edx/app/edxapp/edxapp_env
cd /edx/app/edxapp/edx-platform
python scripts/trans.py --all --settings=devstack_docker
'
```

### 5.3 Sites / Site Configuration / Site Theme ✅

#### Sites (django_site)

```bash
docker exec -i edx.devstack.mysql mysql -uroot edxapp -e "
INSERT INTO django_site (domain, name) VALUES ('0.0.0.0:18000', 'LMS');
INSERT INTO django_site (domain, name) VALUES ('0.0.0.0:18010', 'Studio');
INSERT INTO django_site (domain, name) VALUES ('localhost:18000', 'LMS-localhost');
INSERT INTO django_site (domain, name) VALUES ('localhost:18010', 'Studio-localhost');
"
```

#### Site Configuration (same as remote Triboo JSON)

Full JSON matches remote config. Key setting: `COURSE_CATALOG_API_URL: http://edx.devstack.discovery:18381/api/v1/`.

#### Site Theme (hawthorn)

```bash
docker exec -i edx.devstack.mysql mysql -uroot edxapp -e "
INSERT INTO theming_sitetheme (site_id, theme_dir_name) VALUES (2, 'hawthorn'), (3, 'hawthorn');
"
```

#### Enable Comprehensive Theming

```bash
# LMS
docker exec edx.devstack.lms python -c "
import json
with open('/edx/app/edxapp/lms.env.json') as f:
    d = json.load(f)
d['COMPREHENSIVE_THEME_DIRS'] = ['/edx/src/themes/']
d['ENABLE_COMPREHENSIVE_THEMING'] = True
with open('/edx/app/edxapp/lms.env.json', 'w') as f:
    json.dump(d, f, indent=2)
"

# Studio (same, file is cms.env.json)
```

Theme files located at `src/themes/hawthorn/`, already present in local repo.

---

## 6. Common Troubleshooting Reference

All commands use `docker compose` and `docker exec` syntax, verified working on OrbStack.

### ImportError

| Error | Fix |
|-------|-----|
| `No module named ldap` | pip install python-ldap==2.4.44 + libldap2-dev first |
| `No module named saml2` | pip install pysaml2==4.9.0 + xmlsec1 first |
| `No module named django_tables2` | pip install django-tables2==1.16.0 |
| `No module named rest_framework_nested` | pip install drf-nested-routers==0.91 |
| `No module named search.search_engine_base` | pip install -e /edx/app/edxapp/edx-search |
| `No module named edx_proctoring` | Sync venv/src/ from remote + pip install -e |
| `ImportError ... tz` | `docker restart edx.devstack.memcached` |
| `libffi-xxx.so: cannot open` | pip uninstall cffi cryptography && install libffi-dev && pip install cffi==1.11.5 cryptography==2.2.2 |

### Runtime Errors

| Error | Fix |
|-------|-----|
| LMS/Studio ImportError cascade | Sync site-packages + venv/src from remote |
| Login page 500 | `docker exec edx.devstack.lms ... paver update_db --settings devstack_docker` |
| `webpack-stats.json` missing (Studio) | Run `paver update_assets cms` in Studio container |
| `LanguageSelector is not defined` | Re-run `paver update_assets --settings devstack_docker` |
| `Table ... doesn't exist` | `docker exec -i edx.devstack.mysql mysql -uroot edxapp < xxx.sql` |

### Build Failures

| Error | Fix |
|-------|-----|
| `Build failed: update_assets` | `docker exec edx.devstack.lms ... paver update_assets --settings devstack_docker` |
| `node-sass ... requires node >=14` | Upgrade Node to 16.20.2 (see issue 5) |
| `npm ERR! ENOTEMPTY` | `docker volume rm devstack_edxapp_node_modules` + delete host node_modules |

### Search/Catalog

`An error occurred when searching` → Comment out line 36 of provision-lms.sh and re-run provision.

### Courses Not Displaying

```bash
./provision-discovery.sh
# In lms container:
python manage.py lms reindex_course --all --reconfig
python manage.py cms reindex_course --all --reconfig
```

---

## 7. Commonly Used Commands

```bash
export DEVSTACK_WORKSPACE=/Users/noahwang/workspace/hawthorn
cd $DEVSTACK_WORKSPACE/devstack

# Start all base services
docker compose -f docker-compose.yml up -d mysql mongo memcached elasticsearch devpi

# Start LMS + Studio (with source mount)
DEVSTACK_WORKSPACE=$DEVSTACK_WORKSPACE docker compose -f docker-compose.yml -f docker-compose-host.yml up -d lms studio

# Initialize database
docker exec -i edx.devstack.mysql mysql -uroot mysql < provision.sql
docker exec -i edx.devstack.mongo mongo < mongo-provision.js

# Enter container shell
docker exec -it edx.devstack.lms bash -c 'source /edx/app/edxapp/edxapp_env && bash'
# Or via make (requires TTY): make lms-shell / make studio-shell

# View logs
docker logs -f edx.devstack.lms
docker logs --tail 50 edx.devstack.lms

# Restart
docker restart edx.devstack.lms edx.devstack.studio

# Full cleanup
docker compose -f docker-compose.yml -f docker-compose-host.yml down -v
```

---

## 8. Local Modifications

### docker-compose.yml

| Modification | Detail |
|-------------|--------|
| All 10 services | Added `platform: linux/amd64` |
| memcached | Image `1.4.24` → `1.5.4` |

### In-Container Modifications (non-persistent, redo on container rebuild)

| Modification | Detail |
|-------------|--------|
| Node version | /edx/app/edxapp/nodeenvs/edxapp → Node 16.20.2 |
| System packages | libldap2-dev, libsasl2-dev, libffi-dev, xmlsec1 |
| site-packages | Synced from remote |
| venv/src | Synced from remote (xblock and local packages) |

---

## 9. Local vs Remote Differences

| Dimension | Remote (VMware x86) | Local (OrbStack ARM) |
|-----------|---------------------|----------------------|
| platform directive | Not needed | `platform: linux/amd64` |
| memcached | 1.4.24 | 1.5.4 |
| Node | v16.20.2 | v16.20.2 (manual upgrade) |
| DEVSTACK_WORKSPACE | /home/noahwang/workspace/hawthorn | /Users/noahwang/workspace/hawthorn |
| MySQL port | 3306 | 3306 |
| Container network | Internal net outbound OK | Proxy-restricted |
