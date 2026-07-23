# 依赖桥 — 兼容性盲区与阻塞点

> Date: 2026-07-23 · ⚠️ 2026-07-23 更新：Python target 改为 **3.6**（py36-probe-result-20260723.md）。celery/kombu/edx-celeryutils 桥不再需要。
> PyPI 实时查询结果
>
> **⚠️ 2026-07-23 reconcile**: 本文档早期 target（mongoengine 0.19.1 / pymongo 3.12-3.13 / celery 3-5d）已被 `juniper-dependency-comparison.md` 修正。以本文 §1/§4/§5 现值（mongoengine 0.10.0 不动 / pymongo 3.9.0 / celery 5-7d）为准。原 fallback 行的"Juniper 验证 3.12.3"是笔误，Juniper 验证的是 3.9。

---

## 1. 桥版本真伪验证

| 包 | Bridge 目标 | Py2? | Py3.8? | 真桥？ | 备注 |
|------|------|:---:|:---:|:---:|------|
| mysqlclient | 1.4.6 | ✅ | ✅ | ✅ 真桥 | `python_requires` 未设 = 全版本兼容 |
| pymongo | 3.9.0 | ✅ | ✅ | ✅ 真桥 | **target 3.9.0（与 Juniper 一致；已验证 mongoengine 0.10.0 + pymongo 3.9 兼容）**。3.12.3/3.13.0 亦可（无 python_requires 限制）作 fallback。4.x 起要求 ≥3.7 |
| mongoengine | 0.10.0 | ✅ | ⚠️ 待 smoke | ⚠️ 灰桥 | **target 0.10.0 不动（Juniper 验证 0.10.0 + pymongo 3.9 在 Py3 兼容；实际使用仅 5 文件：dashboard/{models,git_import,sysadmin} + xmodule/modulestore/mongoengine_fields，风险被天然隔离）**。0.18.2/0.19.1 是 fallback（classifiers 标 Py3.5/3.6，0.19.1 是最后带 Py2 版本）。0.10.0 早于官方 Py3 支持，需在 py 容器对 5 文件定点 smoke |
| python-memcached | 1.59 | ✅ | ✅ | ✅ 真桥 | 1.59–1.62 均无 python_requires 限制 |
| celery | 4.4.7 | ✅ (≥2.7) | ✅ (≥3.5) | ✅ 真桥 | 明确定义 `>=2.7, !=3.0-3.4.*` |
| kombu | 4.6.11 | ✅ (≥2.7) | ✅ (≥3.5) | ✅ 真桥 | 同 celery |
| Django | 1.11.29 | ✅ | ⚠️ 未验证 | ⚠️ 灰桥 | 官方 Py3 测试止步 3.7。3.8 **从未测试**。`python_requires` 未设所以安装不会阻止，但运行时未知 |
| **edx-celeryutils** | 0.2.7 → ??? | — | — | 🔴 **无桥** | 见下节 |

---

## 2. edx-celeryutils — 唯一「无桥」组件

### 版本分叉

| 版本 | celery 约束 | Python | 说明 |
|------|------|------|------|
| 0.2.7 (当前) | `celery>=3.1.25,<4.0` | Py2 + Py3 | 🔴 **明确禁止 celery 4.x** |
| 1.x | 未查 | 未查 | 中间版本 |
| 2.0.0 | `celery<6.0` | Py3.12 only | ✅ 允许 celery 4.x，但 🔴 丢弃 Py2 |

**无版本同时满足：允许 celery ≥4.0 且支持 Python 2.7。**

### 我们用了 edx-celeryutils 的哪些功能？

```
LoggedPersistOnFailureTask  — 6 个模块 (grades, certificates, triboo_analytics, contentstore, course_overviews, schedules)
LoggedTask                  — 3 个模块 (program_enrollments, discussion, schedules)
chord / chord_task          — 1 个模块 (contentstore/tasks.py)
```

全部是 celery Task 子类的薄包装：
- `LoggedPersistOnFailureTask` ≈ celery Task + `on_failure` 日志
- `LoggedTask` ≈ celery Task + `after_return` 日志
- `chord` ≈ 封装的 celery chord

### 解决方案（三选一）

| 方案 | 做法 | 风险 | 推荐 |
|------|------|:---:|:---:|
| **A. Fork** | Fork edx-celeryutils 0.2.7，改 celery pin 为 `<5.0`，修 Task API 兼容 celery 4.4 | 低（改动量小） | ⭐ 推荐 |
| **B. Inline** | 把 3 个类直接搬进 platform，去掉 edx-celeryutils 依赖 | 中（10 个引用点需改 import） | 备选 |
| **C. 先跳再降** | pip install 时 ignore pin，装 celery 4.4 + edx-celeryutils 0.2.7，运行时修 | 高（隐藏的 API 不兼容） | 不推荐 |

**推荐方案 A**：fork 到 `Learningtribes/edx-celeryutils`，只改两处：
1. `setup.py`: `'celery>=3.1.25,<4.0'` → `'celery>=3.1.25,<5.0'`
2. `LoggedPersistOnFailureTask` / `LoggedTask`: 适配 celery 4.x 的 Task API（`on_failure` 签名变更）

---

## 3. Django 1.11.29 on Python 3.8 — 灰桥

### 风险分析

Django 1.11 官方支持矩阵：
- Python 2.7 ✅
- Python 3.4 ✅
- Python 3.5 ✅
- Python 3.6 ✅（1.11.1+）
- Python 3.7 ✅（1.11.17+）
- Python 3.8 ❌ **从未官方测试**

**但上游 Open edX Juniper 在 Django 2.2 上跑 Py3，没有走过 1.11+Py3.8。** 这是我们特有的风险。

### 具体担忧

| 方面 | 风险 | 说明 |
|------|:---:|------|
| `collections.abc` 移动 | 低 | 1.11 已通过 `six` 处理 |
| `async`/`await` 关键字 | 低 | 1.11 不含 async 代码 |
| `time.clock()` 移除 | 中 | Py3.8 移除，Django 1.11 某些 profiler 可能调它 |
| `importlib` 变更 | 低 | 1.11 的 `import_module` 是稳定的 |
| 第三方中间件 | 中 | `django-celery-beat`、`social-auth` 等中间件未在 1.11+3.8 上测试 |

### 缓解

```bash
# 在 py38 容器中做 smoke spike
docker exec -w /work py38-tool-container python3 -c "
import django
django.setup()
from django.core.management import call_command
call_command('check')
"
```

通过了 = 灰桥转白。失败了 = 需回退到 Django 2.2 方案（但会切断 Py2 兼容 → 必须在 Py3 cutover 同时升级 Django）。

---

## 4. Py2→Py3 版本断裂点总图

```
包                  当前           Bridge            Py3-only
──────────────────────────────────────────────────────────────
mysqlclient         1.2.5          1.4.6       ←→    2.x (≥3.8)
pymongo             2.9.1          3.9.0       ←→    4.x (≥3.7)    (3.12/3.13 fallback)
mongoengine         0.10.0         0.10.0(不动) ←→    0.20+ (≥3.5)  (0.18.2/0.19.1 fallback)
python-memcached    1.48           1.59–1.62   ←→    1.62+ (未声明)
celery              3.1.25         4.4.7       ←→    5.x (≥3.8)
kombu               3.0.37         4.6.11      ←→    5.x (≥3.8)
redis-py            2.10.6         3.5.x       解耦   4.x (≥3.6)
elasticsearch-py    1.9.0          保持不变    ←→    7.x (≥3.6)
Django              1.11.15  ⚠️    1.11.29     跳→   2.2 (≥3.5, 丢Py2)
edx-celeryutils     0.2.7    🔴    FORK 需     跳→   2.0 (≥3.12, 丢Py2)

图例：←→ = 有桥（Py2+Py3 双兼容） | 跳→ = 无桥（Py3-only，需在 cutover 时同步跳）
       ⚠️ = 有桥但 Py3.8 未验证 | 🔴 = 无桥需 fork
```

---

## 5. 修正后的 Batch 1 执行计划

```
1. mysqlclient 1.4.6                          🟢 0.5d  直换
2. pymongo 3.9.0 + mongoengine 0.10.0(不动)  🟢 0.5d  直换 + 5 文件 smoke（0.10.0 在 Py3.8 待验）
3. python-memcached 1.59                      🟢 0.5d  直换
4. FORK edx-celeryutils (pin → <5.0)          🟡 1d    fork + 验证
5. celery 4.4.7 + kombu 4.6.11                🔴 5-7d  配置/settings/import + 61 @task→@shared_task + instructor_task 14 decorator + 3 wrapper 类
6. Django 1.11.29 + Py3.8 smoke spike         🟡 0.5d  django.setup() + check
7. pip install -r requirements → 全量安装      🟢 0.5d  解决依赖冲突
                                     ─────────
                                     总计 ~9-12d（若 target Py3.6：celery/kombu/edx-celeryutils 跳过 → ~2d）
```

---

## 6. 如果桥断裂怎么办？

| 断裂场景 | 后备方案 |
|------|------|
| Django 1.11.29 在 Py3.8 上通不过 smoke | → 切换到 Django 2.2.28（但需同时 cut over Py3，Py2 不再支持） |
| edx-celeryutils fork 后 celery 4.4 仍有阻塞 | → Inline 方案 B（10 个文件改 import） |
| mongoengine 0.10.0 在 Py3.8 smoke 失败 | → 升到 0.18.2/0.19.1（classifiers 标 Py3.5/3.6，0.19.1 最后带 Py2） |
| pymongo 3.9.0 ModuleStore 回归失败 | → 升到 3.12.3/3.13.0（无 python_requires 限制；注：Juniper 验证的是 3.9，非 3.12） |
