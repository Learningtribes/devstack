# Hawthorn Devstack — Mac M5 + OrbStack 搭建完整记录

> Apple Silicon (M5) + OrbStack 2.2.1 + macOS Tahoe 26.5.1  
> 日期: 2026-07-18  
> 结果: ✅ LMS (18000) + Studio (18010) 全服务正常运行

---

## 一、前置准备

### 环境

| 项目 | 值 |
|------|-----|
| 本地路径 | `/Users/noahwang/workspace/hawthorn/devstack` |
| 远程参考 | `pcupgrade_nat` (VMware on Win11, 内网) |
| 工作空间变量 | `DEVSTACK_WORKSPACE=/Users/noahwang/workspace/hawthorn` |
| 登录账号 | `edx` / `edx` |

### 已安装工具

- OrbStack 2.2.1（替代 Docker Desktop）
- Rosetta 转译已启用（`orb config get rosetta` → true）

### 镜像清单

| 镜像 | 大小 | 架构 |
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

## 二、问题与解决

### 1. 镜像架构不兼容

**问题:** `docker compose pull` 报错 `no matching manifest for linux/arm64/v8`

**原因:** 所有 devstack 镜像都是 x86 架构，没有 ARM64 版本。

**解决:** docker-compose.yml 中每个 service 添加 `platform: linux/amd64`

```yaml
services:
  mysql:
    image: mysql:5.6
    platform: linux/amd64
```

### 2. memcached manifest v1 不兼容

**问题:** `memcached:1.4.24` 使用 manifest v1 格式，OrbStack containerd v2.1 不支持。

**解决:** 升级到 `memcached:1.5.4`（使用 manifest v2）。作为纯缓存，版本升级无影响。

### 3. Docker Hub 镜像拉取缓慢

**问题:** Docker registry mirror（1ms.run, xuanyuan.me, daocloud.io）对老旧大镜像限速。

**解决:** 临时清空 `~/.orbstack/config/docker.json` 中的 registry-mirrors 直连 Docker Hub，拉取完后恢复。

```bash
echo '{"registry-mirrors": []}' > ~/.orbstack/config/docker.json
orb restart docker
```

### 4. DEVSTACK_WORKSPACE 环境变量未设置

**问题:** `/edx/app/edxapp/edx-platform` 挂载为空，只有 node_modules volume。

**解决:** 所有 docker compose 命令必须带 `DEVSTACK_WORKSPACE`：

```bash
export DEVSTACK_WORKSPACE=/Users/noahwang/workspace/hawthorn
DEVSTACK_WORKSPACE=$DEVSTACK_WORKSPACE docker compose -f docker-compose.yml -f docker-compose-host.yml up -d lms studio
```

### 5. Node.js 版本过旧 (v8.9.3 → v16.20.2)

**问题:** 容器内置 Node v8.9.3，但 edx-platform 的 `node-sass: ^8` 需要 Node 14+。

**解决:** 宿主机下载 Node 16.20.2 二进制，通过 bind mount 传入容器解压到 nodeenv：

```bash
# 宿主机
curl -sL https://nodejs.org/dist/v16.20.2/node-v16.20.2-linux-x64.tar.gz -o /tmp/n16.tar.gz
cp /tmp/n16.tar.gz $DEVSTACK_WORKSPACE/platform/

# 容器内
source /edx/app/edxapp/edxapp_env
rm -rf /edx/app/edxapp/nodeenvs/edxapp
mkdir -p /edx/app/edxapp/nodeenvs/edxapp
tar xzf /edx/app/edxapp/edx-platform/n16.tar.gz --strip-components=1 -C /edx/app/edxapp/nodeenvs/edxapp
```

### 6. npm install 残留 node_modules 损坏

**问题:** 多次 npm install 失败后，volume 和宿主目录有残留损坏文件（`ENOTEMPTY`）。

**解决:** 彻底清理后重建：

```bash
docker rm -f edx.devstack.lms edx.devstack.studio
docker volume rm devstack_edxapp_node_modules
rm -rf $DEVSTACK_WORKSPACE/platform/node_modules
```

### 7. 容器内网络受限

**问题:** 容器内无法访问外网（apt-get、nodeenv 下载均超时）。

**原因:** OrbStack 容器通过宿主机代理，代理不稳定。

**解决模式:** 需要外网资源时，宿主机下载 → bind mount 传入容器。
- Node 二进制 → 宿主机 curl 下载
- .deb 包 → 宿主机从 Ubuntu archive 下载
- pip 包 → 通过 devpi 缓存 + 远程同步

### 8. python-ldap 缺失 + 编译链缺失

**问题:** LMS 启动报 `ImportError: No module named ldap`。ltdps/edxapp 镜像的 venv 缺 python-ldap 和 django-auth-ldap。

**解决:**
1. 宿主机下载 libldap2-dev、libsasl2-dev 等 .deb
2. 注入容器 `dpkg -i`
3. pip install python-ldap==2.4.44 django-auth-ldap==1.2.15

```bash
# 宿主机
curl -sL "http://archive.ubuntu.com/ubuntu/pool/main/o/openldap/libldap2-dev_2.4.42+dfsg-2ubuntu3.13_amd64.deb" -o /tmp/libldap2-dev.deb
curl -sL "http://archive.ubuntu.com/ubuntu/pool/main/c/cyrus-sasl2/libsasl2-dev_2.1.26.dfsg1-14ubuntu0.2_amd64.deb" -o /tmp/libsasl2-dev.deb
# ... 同样下载 libldap-2.4-2, libsasl2-2, libkrb5-dev
cp /tmp/*.deb $DEVSTACK_WORKSPACE/platform/

# 容器内
cd /edx/app/edxapp/edx-platform
dpkg -i libldap*.deb libsasl*.deb libkrb5*.deb
source /edx/app/edxapp/edxapp_env
pip install python-ldap==2.4.44 django-auth-ldap==1.2.15
```

### 9. pysaml2 + xmlsec1 缺失

**问题:** ldap 通过后报 `ImportError: No module named saml2`，装完后报 `SigverError: Cannot find xmlsec1`。

**解决:**
1. pip install pysaml2==4.9.0（devpi 有 wheel）
2. 宿主机下载 xmlsec1 .deb 注入

```bash
curl -sL "http://archive.ubuntu.com/ubuntu/pool/main/x/xmlsec1/xmlsec1_1.2.20-2ubuntu4_amd64.deb" -o /tmp/xmlsec1.deb
```

### 10. django-tables2 Python 2 兼容问题

**问题:** pip 拉取最新 django-tables2 3.0.0 在 Python 2.7 下 SyntaxError（Non-ASCII character）。

**解决:** 装远程同款版本 `django-tables2==1.16.0`。

### 11. drf-nested-routers Python 版本要求

**问题:** 最新版要求 Python >= 3.8。

**解决:** 装老版本 `drf-nested-routers==0.91`。

### 12. 缺失包级联（核心策略：从远程同步 site-packages）

**问题:** 逐个修包遇到大量级联 ImportError，且 pip 下载慢。

**解决:** 直接从远程 devstack 导出完整 site-packages + venv/src 到本地覆盖：

```bash
# 远程导出
ssh -J home_zyw pcupgrade_nat 'docker cp edx.devstack.lms:/edx/app/edxapp/venvs/edxapp/lib/python2.7/site-packages /tmp/remote_sp; cd /tmp && tar czf sp.tar.gz remote_sp'
scp -o ProxyJump=home_zyw pcupgrade_nat:/tmp/sp.tar.gz /tmp/
# 同理导出 venv/src

# 本地注入
# site-packages: 解压后替换 /edx/app/edxapp/venvs/edxapp/lib/python2.7/site-packages
# venv/src: 解压后放到 /edx/app/edxapp/venvs/edxapp/src
# 然后 pip install -e 每个 src 下的包
```

### 13. cffi/cryptography 编译共享库不匹配

**问题:** 复制远程 site-packages 后，cryptography 报 `libffi-xxx.so.6.0.4: cannot open shared object file`。远程 cffi 编译时链了特定版本 libffi。

**解决:** 本地重装（编译）cffi 和 cryptography：

```bash
pip uninstall -y cffi cryptography
# 先装 libffi-dev（下载 .deb 注入）
dpkg -i libffi-dev*.deb
pip install cffi==1.11.5 cryptography==2.2.2
```

**关键:** 必须指定确切版本号，否则 pip 拉最新版会 Python 2 不兼容。必须从源码编译（不能用 wheel），因为 wheel 链接的 libffi 可能不同。

### 14. edx-search 未注册为 Python 包

**问题:** LMS 报 `No module named search.search_engine_base`。文件在 `/edx/app/edxapp/edx-search/` 但未 pip install。

**解决:**
```bash
pip install -e /edx/app/edxapp/edx-search
```

### 15. edx_proctoring 等本地包缺失

**问题:** 复制远程 site-packages 后，.egg-link 指向的路径不匹配。

**解决:** 导出远程 `venvs/edxapp/src/` 目录到本地，然后 pip install -e 每个包。

### 16. LMS 登录页 500 — 数据库未迁移

**问题:** LMS 和 Studio 启动后 /login 返回 500。

**解决:** 运行 migration：

```bash
docker exec edx.devstack.lms bash -c '
source /edx/app/edxapp/edxapp_env
cd /edx/app/edxapp/edx-platform
paver update_db --settings devstack_docker
'
```

### 17. Ansible demo course 安装卡死

**问题:** provision 脚本中 ansible-playbook 尝试 apt-get install 系统包，容器内无网卡死。

**解决:** 跳过 demo course（非必需）。

### 18. Studio 找不到 webpack-stats.json

**问题:** 最初试图 LMS 共享给 Studio，但正确做法是各容器独立编译。

**正确解法:** LMS 和 Studio 分别在自己的容器编译：
```bash
# LMS 容器内
paver update_assets lms --settings=devstack_docker

# Studio 容器内
paver update_assets cms --settings=devstack_docker
```
如果 Studio 的 webpack 步骤因网络问题失败，分步执行：
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

### 20. Studio 日志目录缺失

**问题:** `No such file or directory: '/edx/var/log/lms/metrics_page_views_logger.csv'`

**解决:**
```bash
docker exec edx.devstack.lms mkdir -p /edx/var/log/lms /edx/var/log/cms
docker exec edx.devstack.studio mkdir -p /edx/var/log/lms /edx/var/log/cms
```

### 23. LMS 修复未同步到 Studio（核心教训）

**问题:** LMS 做了全套修复后能正常运行，但 Studio 仍然各种报错（xmlsec1 缺失、node-sass binding 不兼容、ldap 等 ImportError）。根因是有大量修复只对 LMS 容器做了，Studio 容器是独立实例，需要**逐项同步**。

**需要同步到 Studio 的修复清单：**

| # | 修复项 | LMS 状态 | Studio 状态 | 操作 |
|---|--------|---------|------------|------|
| 1 | Node 8 → 16 | ✅ | ❌→✅ | 解压 n16.tar.gz 到 nodeenvs/edxapp |
| 2 | libldap2-dev + libsasl2-dev | ✅ | ❌→✅ | dpkg -i .deb |
| 3 | libffi-dev | ✅ | ❌→✅ | dpkg -i .deb |
| 4 | xmlsec1 | ✅ | ❌→✅ | dpkg -i .deb |
| 5 | site-packages 替换 | ✅ | ❌ | 从远程同步（与 LMS 共用同一份） |
| 6 | venv/src 同步 | ✅ | ❌ | 从远程同步 |
| 7 | pip install -e src/* | ✅ | ✅ | 已在 site-packages 同步时完成 |
| 8 | cffi + cryptography 重编译 | ✅ | ✅ | 需在 Studio 容器内重做 |
| 9 | edx-search pip install -e | ✅ | ❌→✅ | 挂载已生效，但 egg-link 需确认 |
| 10 | node-sass rebuild | ✅ | ❌→✅ | Node 升级后必须 rebuild |
| 11 | edx-platform setup.py develop | ✅ | ✅ | 挂载已生效 |
| 12 | paver update_assets | ✅ | ❌ | webpack-stats.json 从 LMS 拷，Sass+collectstatic 分步跑 |

**关键原则:** LMS 和 Studio 是同一镜像但独立容器，任何容器内修改（系统包、nodeenv、pip install）都需要**两边各做一遍**。只有通过 bind mount 共享的目录（platform、themes、edx-search）是两边同步的。

### 21. Sites 域名匹配

**问题:** 用 `localhost:18000` 访问无 theme/配置，`0.0.0.0:18000` 正常。

**原因:** Django Sites 框架根据请求 Host header 匹配 `django_site.domain`。

**解决:** 添加 localhost 站点记录，配置和 theme 与 0.0.0.0 相同。

### 22. Theme CSS 编译

**问题:** 启用 comprehensive theming 后 theme 不生效。

**正确流程:**
1. `git pull` 确保 theme 仓库最新（CSS 在 git 中）
2. 修改 `lms.env.json` / `cms.env.json`:
   - `ENABLE_COMPREHENSIVE_THEMING: true`
   - `COMPREHENSIVE_THEME_DIRS: ["/edx/src/themes/"]`
3. MySQL 插入: `django_site` → `site_configuration_siteconfiguration` → `theming_sitetheme`
4. `paver update_assets lms --settings=devstack_docker` (会编译 theme SCSS)
5. 重启容器

---

## 三、最终状态

### 运行中服务

| 服务 | 端口 | 状态 |
|------|------|------|
| MySQL | 3306 | ✅ |
| MongoDB | 27017 | ✅ |
| Elasticsearch | 9200 | ✅ |
| Memcached | 11211 | ✅ |
| Devpi | 3141 | ✅ |
| LMS | 18000 | ✅ |
| Studio | 18010 | ✅ |

### 验证

```bash
curl -o /dev/null -w "%{http_code}" http://localhost:18000/login   # 200
curl -o /dev/null -w "%{http_code}" http://localhost:18010/signin  # 200
curl -o /dev/null -w "%{http_code}" http://localhost:18010/        # 302
```

### 未完成（非阻塞）

- demo course 创建（容器无网，ansible apt 卡死）
- 其他 IDA 服务（discovery, ecommerce, forum）未启动

### 已完成 ✅

- MySQL 默认配置（auth groups, waffle switches 等）
- 翻译文件生成
- Sites 配置（LMS: 0.0.0.0:18000, Studio: 0.0.0.0:18010）
- Site Configuration（同远程 Triboo JSON）
- Site Theme（hawthorn）+ comprehensive theming 启用

---

## 四、标准 devstack 步骤 → 手动等价对照

标准文档要求 `make dev.provision` 一键完成，但 M5 + OrbStack 下每一步都需手动替代。以下是完整对照：

| # | 标准步骤 | 等价手动操作 | 备注 |
|---|---------|-------------|------|
| 1 | `export OPENEDX_RELEASE=...` | 跳过 | 本地仓库已在 workspace |
| 2 | `virtualenv .venv && make requirements` | 跳过 | 不经过宿主机 Python，直接操作容器 |
| 3 | `make dev.clone` | 跳过 | 仓库已 clone |
| 4 | `make dev.provision` | 见下分解 | 全程手动 |
| 4a | └ `docker-compose up -d mysql mongo` | `docker compose -f docker-compose.yml up -d mysql mongo` | 同 |
| 4b | └ `provision.sql + mongo-provision.js` | `docker exec -i ... mysql < provision.sql` + mongo 同理 | 同 |
| 4c | └ `provision-lms.sh` | 手动分步（见 4c-1 ~ 4c-8） | 见问题 5-16 |
| 4c-1 | └─ `load-db.sh` | 同，DB dump 本地已有 | ✅ |
| 4c-2 | └─ `docker-compose up lms studio` | `DEVSTACK_WORKSPACE=... docker compose -f ... -f ... up -d lms studio` | 必须带 DEVSTACK_WORKSPACE |
| 4c-3 | └─ `paver install_prereqs` | 手动：升级 Node 16 → npm install → pip install 缺失包 → 同步远程 site-packages | 见问题 5-15 |
| 4c-4 | └─ `docker-compose restart lms` | `docker restart edx.devstack.lms` | 同 |
| 4c-5 | └─ `paver update_db` | `docker exec ... paver update_db --settings devstack_docker` | ✅ 已执行 |
| 4c-6 | └─ 创建 superuser | `docker exec ... manage_user edx ...` | ✅ edx/edx |
| 4c-7 | └─ ansible demo course | **跳过**（容器无网，ansible apt 卡死） | ❌ |
| 4c-8 | └─ `paver update_assets` | `docker exec ... paver update_assets --settings devstack_docker` | ✅ LMS 容器执行 |
| 5 | `make dev.up` | `docker compose ... up -d lms studio` | 同 |
| 6 | `make lms-shell && apt-get install` | 宿主机下载 .deb → bind mount → dpkg -i | 容器无网替代方案 |
| 7 | MySQL 默认配置 | `docker exec -i edx.devstack.mysql mysql -uroot edxapp < sql` | ✅ 已执行 |
| 8 | 翻译文件生成 | `docker exec ... python scripts/trans.py --all` | ✅ 已执行 |

### 可忽略/跳过的

| 步骤 | 理由 |
|------|------|
| `make dev.up.watchers` (asset watchers) | 不开发前端可跳过 |
| chrome/firefox 容器 | 仅 e2e 测试，compose 中已注释 |
| edx-notes-api / credentials / xqueue | compose 中已注释 |
| forum / discovery / ecommerce | 非核心开发可暂不启动 |
| virtualenv / conda | 宿主机不需要 Python 环境 |

---

## 五、已完成配置（2026-07-18 已执行验证）

### 5.1 MySQL 默认配置 ✅

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

### 5.2 翻译文件生成 ✅

```bash
docker exec edx.devstack.lms bash -c '
source /edx/app/edxapp/edxapp_env
cd /edx/app/edxapp/edx-platform
python scripts/trans.py --all --settings=devstack_docker
'
```

### 5.3 Sites / Site Configuration / Site Theme ✅

#### Sites（django_site）

```bash
docker exec -i edx.devstack.mysql mysql -uroot edxapp -e "
INSERT INTO django_site (domain, name) VALUES ('0.0.0.0:18000', 'LMS');
INSERT INTO django_site (domain, name) VALUES ('0.0.0.0:18010', 'Studio');
"
```

#### Site Configuration（同远程 Triboo JSON）

```bash
docker exec -i edx.devstack.mysql mysql -uroot edxapp -e "
INSERT INTO site_configuration_siteconfiguration (site_id, enabled, \`values\`)
VALUES (2, 1, '{\"PLATFORM_NAME\":\"Triboo\",...}');
INSERT INTO site_configuration_siteconfiguration (site_id, enabled, \`values\`)
VALUES (3, 1, '{\"PLATFORM_NAME\":\"Triboo\",...}');
"
```

完整 JSON 见上文第五章 5.1 中的配置（与远程一致，本地使用 `COURSE_CATALOG_API_URL: http://edx.devstack.discovery:18381/api/v1/`）。

#### Site Theme（hawthorn）

```bash
docker exec -i edx.devstack.mysql mysql -uroot edxapp -e "
INSERT INTO theming_sitetheme (site_id, theme_dir_name) VALUES (2, 'hawthorn'), (3, 'hawthorn');
"
```

#### 启用 Comprehensive Theming

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

# Studio (同理，文件为 cms.env.json)
```

Theme 文件位于 `src/themes/hawthorn/`，已存在于本地仓库。

---

## 六、常见故障速查（已用实际语法验证）

以下命令均使用 `docker compose` 和 `docker exec` 语法，在 OrbStack 环境下已验证可用。

### ImportError 类

| 错误 | 修复命令 |
|------|---------|
| `No module named ldap` | pip install python-ldap==2.4.44 + 先装 libldap2-dev |
| `No module named saml2` | pip install pysaml2==4.9.0 + 先装 xmlsec1 |
| `No module named django_tables2` | pip install django-tables2==1.16.0 |
| `No module named rest_framework_nested` | pip install drf-nested-routers==0.91 |
| `No module named search.search_engine_base` | pip install -e /edx/app/edxapp/edx-search |
| `No module named edx_proctoring` | 从远程同步 venv/src/ + pip install -e |
| `ImportError ... tz` | `docker restart edx.devstack.memcached` |
| `libffi-xxx.so: cannot open` | pip uninstall cffi cryptography && 装 libffi-dev && pip install cffi==1.11.5 cryptography==2.2.2 |

### 运行时错误

| 错误 | 修复命令 |
|------|---------|
| LMS/Studio 启动 ImportError 级联 | 从远程 devstack 同步 site-packages + venv/src |
| 登录页 500 | `docker exec edx.devstack.lms ... paver update_db --settings devstack_docker` |
| `webpack-stats.json` 缺失 (Studio) | 从 LMS 容器拷到 Studio 容器 volume（见问题 18） |
| `LanguageSelector is not defined` | 重新 `paver update_assets --settings devstack_docker` |
| `Table ... doesn't exist` | `docker exec -i edx.devstack.mysql mysql -uroot edxapp < xxx.sql` |

### 构建失败

| 错误 | 修复命令 |
|------|---------|
| `Build failed: update_assets` | `docker exec edx.devstack.lms ... paver update_assets --settings devstack_docker` |
| `node-sass ... requires node >=14` | 升级 Node 到 16.20.2（见问题 5） |
| `npm ERR! ENOTEMPTY` | `docker volume rm devstack_edxapp_node_modules` + 删宿主 node_modules |

### 搜索/Catalog

`An error occurred when searching` → 注释 provision-lms.sh 第 36 行重跑 provision

### 课程不显示

```bash
./provision-discovery.sh
# lms 容器内:
python manage.py lms reindex_course --all --reconfig
python manage.py cms reindex_course --all --reconfig
```

---

## 四、常用操作命令

```bash
export DEVSTACK_WORKSPACE=/Users/noahwang/workspace/hawthorn
cd $DEVSTACK_WORKSPACE/devstack

# 起全部底座
docker compose -f docker-compose.yml up -d mysql mongo memcached elasticsearch devpi

# 起 LMS + Studio（带源码挂载）
DEVSTACK_WORKSPACE=$DEVSTACK_WORKSPACE docker compose -f docker-compose.yml -f docker-compose-host.yml up -d lms studio

# 初始化数据库
docker exec -i edx.devstack.mysql mysql -uroot mysql < provision.sql
docker exec -i edx.devstack.mongo mongo < mongo-provision.js

# 进入容器
docker exec -it edx.devstack.lms bash -c 'source /edx/app/edxapp/edxapp_env && bash'

# 查看日志
docker logs -f edx.devstack.lms
docker logs --tail 50 edx.devstack.lms

# 重启
docker restart edx.devstack.lms edx.devstack.studio

# 完全清理
docker compose -f docker-compose.yml -f docker-compose-host.yml down -v
```

---

## 五、本地修改清单

### docker-compose.yml

| 修改 | 内容 |
|------|------|
| 全部 10 个 service | 新增 `platform: linux/amd64` |
| memcached | 镜像从 `1.4.24` → `1.5.4` |

### 容器内修改（非持久，重建容器需重做）

| 修改 | 内容 |
|------|------|
| Node 版本 | /edx/app/edxapp/nodeenvs/edxapp → Node 16.20.2 |
| 系统包 | libldap2-dev, libsasl2-dev, libffi-dev, xmlsec1 |
| site-packages | 从远程同步 |
| venv/src | 从远程同步（xblock 等本地包） |

---

## 六、本地 vs 远程差异

| 维度 | 远程 (VMware x86) | 本地 (OrbStack ARM) |
|------|------------------|---------------------|
| platform 指令 | 无需 | `platform: linux/amd64` |
| memcached | 1.4.24 | 1.5.4 |
| Node | v16.20.2 | v16.20.2（手动升级） |
| DEVSTACK_WORKSPACE | /home/noahwang/workspace/hawthorn | /Users/noahwang/workspace/hawthorn |
| MySQL 端口 | 3306 | 3306 |
| 容器网络 | 内网可出 | 代理受限 |
