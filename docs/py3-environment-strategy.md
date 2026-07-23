# Py3 环境策略 — 与 Py2 Devstack 完全隔离

> Date: 2026-07-23 · ⚠️ 2026-07-23 更新：Python target 改为 **3.6**。celery/kombu 保持 3.1/3.0 不动。
> 原则：当前 Py2 devstack 是生产开发环境，一个字都不能动。Py3 环境完全独立，共享数据库服务。

---

## 1. 双环境架构

```
┌─────────────────────────────────────────────────────────────┐
│ Host (macOS)                                                 │
│                                                              │
│  ┌──────────────────────────┐  ┌──────────────────────────┐ │
│  │  Py2 Devstack（不动）     │  │  Py3.8 Container（新建）  │ │
│  │                          │  │                          │ │
│  │  LMS :18000              │  │  pip install -r py38.txt │ │
│  │  Studio :18010           │  │  celery 4.4, pymongo 3.9 │ │
│  │  celery==3.1.25          │  │  Django 1.11.29          │ │
│  │  pymongo==2.9.1          │  │  mysqlclient 1.4.6       │ │
│  │  MySQL-python 1.2.5      │  │                          │ │
│  │                          │  │  paver test_system       │ │
│  │  ↓ 日常开发使用           │  │  ↓ Py3 验证专用          │ │
│  └────────┬─────────────────┘  └────────┬─────────────────┘ │
│           │                             │                    │
│           └──────────┬──────────────────┘                    │
│                      │                                       │
│          ┌───────────┴───────────┐                          │
│          │  共享数据库服务         │                          │
│          │  MySQL    :3306        │                          │
│          │  MongoDB  :27017       │                          │
│          │  ES       :9200        │                          │
│          │  Memcached :11211      │                          │
│          └───────────────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 需要新建的内容

### 2.1 Py3.8 依赖文件（核心）

当前 Py2 使用 `requirements/edx/base.txt`。Py3 需要一个**独立的依赖文件**，因为多個包需要不同的 pin。

```
requirements/edx/
  ├── base.txt          ← Py2 版本（不动！）
  └── py38-base.txt     ← 新建：Py3.8 版本
```

`py38-base.txt` 的关键差异：

```
# 与 base.txt 相同（不需要版本变化的包 — 直接复用）
-l common.txt

# 以下手动覆盖 pin
Django==1.11.29              # ← base.txt: 1.11.15，升小版本
celery==4.4.7                # ← base.txt: 3.1.25，升大版本
kombu==4.6.11                # ← base.txt: 3.0.37
pymongo==3.9.0               # ← base.txt: 2.9.1
mysqlclient==1.4.6           # ← 替换 MySQL-python==1.2.5
python-memcached==1.59       # ← base.txt: 1.48
redis==3.5.3                 # ← base.txt: 2.10.6
six==1.14.0                  # ← base.txt: 1.11.0
lxml==4.5.0                  # ← base.txt: 3.8.0
Pillow==7.1.2                # ← base.txt: 3.4.0
PyYAML==5.3.1                # ← base.txt: 3.12

# edx-celeryutils — 需要 fork 版本
-e git+https://github.com/Learningtribes/edx-celeryutils@py3-bridge#egg=edx-celeryutils

# 新增 Py3 专用依赖
unicodecsv==0.14.1           # ← csv Py2/3 兼容层（上游 Juniper 也用）
```

### 2.2 Py3.8 venv 容器化

现有 py38-tool-container 只有 5 个 pip 包。需要安装完整依赖：

```bash
# 一次性 setup（在 py38-tool-container 中）
docker exec -w /work py38-tool-container bash -c "
  python3 -m venv /work/.venv-py38
  source /work/.venv-py38/bin/activate
  pip install --upgrade pip setuptools wheel
  pip install -r requirements/edx/py38-base.txt
  pip install -e .
"
```

`.venv-py38` 在 host 的 `platform/` 目录下（bind mount 可见），持久化跨容器重启。

### 2.3 Py3 测试命令

```bash
# 语法检查（已有）
docker exec -w /work py38-tool-container python3 -m compileall -q <module>

# 新：完整测试
docker exec -w /work py38-tool-container bash -c "
  source .venv-py38/bin/activate &&
  python -Wd -m pytest <module> --ds=lms.envs.test -q
"

# 新：Django 管理命令
docker exec -w /work py38-tool-container bash -c "
  source .venv-py38/bin/activate &&
  python manage.py lms check
"
```

---

## 3. 分阶段建立 Py3 环境

### 阶段 1：最小可用（立即可做，不依赖任何东西）

```
目标：pip install 能完成，Django 能 import
```

1. 创建 `requirements/edx/py38-base.txt`
2. 从 `base.txt` 复制内容，逐一替换需要升级的 pin
3. 安装到 `.venv-py38`
4. 验证 `django.setup()` 能跑

**风险**：很多依赖包有复杂的 transitive dependency 冲突。可能需要 `pip-compile` 来解析。

### 阶段 2：Django boot（依赖 Batch 1 部分完成）

```
目标：python manage.py lms check 能跑通
```

1. 修复 Py3 下的 settings 导入问题
2. 处理 Django 1.11 在 Py3.8 下的兼容 warning
3. 数据库连接验证（共享 MySQL/MongoDB）

### 阶段 3：paver test 回路建立

```
目标：pytest --collect-only 至少能收集测试
```

1. 修复 import 错误（如 `import MySQLdb` → 需 mysqlclient）
2. 建立 allow-fail baseline
3. 输出「已知失败数」

---

## 4. 不碰 Py2 devstack 的保证

| 组件 | Py2 devstack | Py3 环境 | 共享？ |
|------|------|------|:---:|
| Python | 2.7.12 | 3.8.20 | ❌ 完全隔离 |
| pip packages | `base.txt` pin | `py38-base.txt` pin | ❌ 不同文件 |
| venv | `/edx/app/edxapp/venvs/edxapp/` | `/work/.venv-py38/` | ❌ 不同路径 |
| 源代码 | `/edx/app/edxapp/edx-platform` | `/work`（同一 host 目录） | ✅ 共享 |
| MySQL | `edx.devstack.mysql:3306` | 同一 host `:3306` | ✅ 共享服务 |
| MongoDB | `edx.devstack.mongo:27017` | 同一 host `:27017` | ✅ 共享服务 |
| ES | `edx.devstack.elasticsearch:9200` | 同一 host `:9200` | ✅ 共享服务 |
| Memcached | `edx.devstack.memcached:11211` | 同一 host `:11211` | ✅ 共享服务 |
| settings | `lms.envs.devstack_docker` | `lms.envs.test`（SQLite? 或用 MySQL test DB） | ⚠️ 需区分 |

**唯一共享的是源代码目录和数据库服务** — 互不干扰。

---

## 5. 前置工作（建环境之前）

### 5.1 先解决 edx-celeryutils fork（0.5 天）

```
# Fork edx-celeryutils to Learningtribes
# 改 setup.py: celery>=3.1.25,<5.0
# 修 Task 子类适配 celery 4.4 API
```

### 5.2 生成 py38-base.txt（0.5 天）

用 `pip-compile` 从 `base.in` 起手，覆盖需要升级的包。或者手工从 `base.txt` 起步替换。

### 5.3 验证 Django 1.11 + Py3.8（0.5 天）

在 py38 容器中 `pip install -e .` 然后 `django.setup()` — 看能不能启动。

---

## 6. 一句话

**Py2 devstack = 生产环境模拟，改动它 = 破坏日常开发。Py3 环境是全新独立的 venv + 独立依赖文件，与 Py2 共享代码和数据库但不共享 Python runtime。**
