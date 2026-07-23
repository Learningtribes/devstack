# Py3 环境供给 Runbook

> Date: 2026-07-23
> 两条流程: ① 从 Py2 devstack 容器提取已装包到 Py3（fresh pip 装不到时的可靠回退）② 把 py36-base.txt 挂载/注入 Py3 容器

---

## 1. 从 Py2 devstack 容器提包到 Py3

### 为什么需要
某些 git pin 在 fresh `pip install` 时会 fallback 到 PyPI 或 404（`#egg=` 与 metadata 名不匹配、上游 org 改名/删除等）。但 **Py2 devstack 容器（`edx.devstack.lms`）的 venv 里已有装好的实物**（`/edx/app/edxapp/venvs/edxapp/...`）—— 直接拷出来最可靠，版本与 prod 完全一致。

### 流程（以 django-cas 为实例）

```bash
PY2_CONTAINER=edx.devstack.lms
PKG=django-cas            # pip 包名
PKG_MOD=django_cas        # import 模块名

# 1. 定位包在 py2 venv 的安装路径 + 文件清单
docker exec $PY2_CONTAINER bash -lc \
  '/edx/app/edxapp/venvs/edxapp/bin/python -m pip show -f '$PKG

# 2. 取出 site-packages 路径
SP=$(docker exec $PY2_CONTAINER bash -lc \
  '/edx/app/edxapp/venvs/edxapp/bin/python -c "import '$PKG_MOD', os; print(os.path.dirname('$PKG_MOD'.__file__))"')
# SP 形如 /edx/app/edxapp/venvs/edxapp/lib/python2.7/site-packages/django_cas

# 3. docker cp 包目录 + egg-info 到 host
DEST=/Users/noahwang/workspace/$PKG_MOD
mkdir -p $DEST
docker cp $PY2_CONTAINER:$SP $DEST/$PKG_MOD
EGG=$(docker exec $PY2_CONTAINER bash -lc \
  "ls -d /edx/app/edxapp/venvs/edxapp/lib/python2.7/site-packages/${PKG_MOD//-/_}-*.egg-info 2>/dev/null" | tr -d '\r')
docker cp $PY2_CONTAINER:$EGG $DEST/${PKG_MOD}-2.1.1.egg-info

# 4. 清 .pyc（Py2 字节码 Py3 无用）
find $DEST -name "*.pyc" -delete
find $DEST -name "__pycache__" -type d -exec rm -rf {} +

# 5. 拷进 py3 容器 + 真跑 import 验 Py3 兼容
docker cp $DEST/$PKG_MOD py36-probe:/tmp/$PKG_MOD
docker exec -w /tmp py36-probe bash -lc '
  python -c "import sys; sys.path.insert(0,\"/tmp\"); import '"$PKG_MOD"'" 2>&1 | tail -5
  # 修暴露的 Py2-ism 后再 import 子模块，验全尾巴
'
```

### django-cas 实例结果（2026-07-23）
- 取出真装 2.1.1（mitodl/django-cas@afac57bc），9 文件 576 行，落 `/Users/noahwang/workspace/django-cas/`
- 真跑 Py3.6 `import django_cas` 暴露:
  - `__init__.py:22 _DEFAULTS.iteritems()` → AttributeError
  - `views.py:3 from urllib import urlencode` → ImportError（**grep 漏的**）
  - 全扫 urllib reorg 跨 6 文件（__init__/models/backends/views/middleware/tests）+ `from StringIO import StringIO` → ~0.5-1d fix
- **但 CAS SSO feature-flagged off**（live `lms.env.json` `AUTH_USE_CAS` absent→False，3 处非测试 import 全门控于 `if FEATURES.get('AUTH_USE_CAS')`），Django 不 import django_cas → **已从 py36-base.txt 删 pin**（根因解，0d）。本流程留作模板 + 若将来启用 CAS 的复用路径。

### ⚠️ 教训
**Py3 兼容验证必须真跑 `import`，不能只 grep。** grep 只能抓 iteritems/print/has_key 等；**抓不到 import 重组类**（`urlparse`→`urllib.parse`、`from urllib import urlencode`→`urllib.parse/urlparse.request`、`StringIO`→`io`）。django-cas 的 urllib reorg 尾巴正是 grep 漏、真跑才暴露的。

---

## 2. py36-base.txt 挂载/注入 Py3 容器

### 文件位置
`devstack/requirements/py36-base.txt`（devstack 仓库内，canonical）。target Python 3.6 专用 —— 含 3.6-specific pin（celery 3.1.25/kombu 3.0.37 不动，省 celery 4.4 迁移 ~5-7d；Django 1.11.29 官方支持 3.6 白桥）。与 platform `requirements/edx/base.txt`（Py2 prod，不动）分离。

### 现状
- 257 行，197 PyPI 包 + git pin
- **django-cas 已删**（CAS off，注释块记录重新启用路径）
- 已知需处理: 3 egg metadata 修复（edx-ora2→`#egg=ora2`、xblock-done→`#egg=lbmdone-xblock`、edx-sga 待核实）+ lbmdone-xblock `importlib.resources` backport（运行时 XBlock，CMS GRADABLE_BLOCKS）+ mysql-python→mysqlclient + beautifulsoup→bs4 + ipaddr（随 #2322 embargo merge 消解）
- 详见 `py36-probe-result-20260723.md` / `py36-git-layer-probe-20260723.md` / `py3-dep-residual-workstream.md`

### 方式 A: docker-compose volume 挂载（推荐，py3 服务加入 compose 时）
```yaml
# docker-compose.yml 新增 py3 服务或 override edxapp
services:
  edxapp-py3:
    image: <py3-image>
    volumes:
      - ../edx-platform:/edx/app/edxapp/edx-platform
      - ./requirements/py36-base.txt:/edx/app/edxapp/edx-platform/requirements/edx/py36-base.txt:ro
    command: bash -c 'pip install -r /edx/app/edxapp/edx-platform/requirements/edx/py36-base.txt && ...'
```

### 方式 B: docker cp 注入（临时/py36-probe 容器）
```bash
docker cp devstack/requirements/py36-base.txt py36-probe:/tmp/py36-base.txt
docker exec py36-probe pip install -r /tmp/py36-base.txt
```

### 独立性原则（见 review-verdict §5）
Py3 env = 全新独立 venv + 独立 `py36-base.txt` + 共享 DB 服务，**不动 Py2 devstack**（改 Py2 devstack = 破坏日常开发）。共享 DB 首次 `migrate` 前须独立 DB 名或 lock，否则毁 Py2 devstack 数据。
