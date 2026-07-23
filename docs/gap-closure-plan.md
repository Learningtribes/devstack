# 补全机制 — 对照上游过渡期的差距清单

> Date: 2026-07-23 · ⚠️ 2026-07-23 更新：Python target 改为 3.6（见 py36-probe-result-20260723.md）。celery/kombu 不再需要升级。
> 参照：上游 dual-stack 过渡期（2019-09-12 → 2019-12-26）的做法

---

## 上游过渡期有什么，我们缺什么

| 上游机制 | 我们有吗 | 差距 |
|------|:---:|------|
| `python-modernize` 批量现代化 | ✅ 已完成 | — |
| Py2 生产上 bake 现代化代码 | ✅ 已在运行 | — |
| **tox py27+py35 同时跑** | ❌ | 🔴 仅 `py_compile` 语法检查 |
| **Py3 allow-fail baseline** | ❌ | 🔴 从未建立 |
| **Py3 test 驱动到零失败** | ❌ | 🔴 从未开始 |
| 依赖升级到 Py3 兼容版本 | ⚠️ 规划了 | 🟡 Batch 1 未执行 |
| celery 在 Py3 下可用 | ❌ | 🔴 3.1 的 kombu.async = SyntaxError |
| `2to3` 清理 `__future__` | N/A | 后续（切換后） |
| 上游 commit 参考 | ⚠️ 有 Juniper 对照 | 🟡 未系统化到流程 |

---

## 补全清单（按优先级）

### M1 — Py3 测试回路（对齐上游 dual-stack 验证能力）

**做什么**：在 py38 容器中建立 allow-fail 测试基线，把不可见的 Py3 测试 backlog 变成可度量数字。

```bash
# 当前状态：仅 compileall
docker exec py38-tool-container python3 -m compileall -q <module>

# 目标状态：真正的 test run（allow-fail）
docker exec py38-tool-container bash -c "
  cd /work && source .venv/bin/activate &&
  pip install -e . &&
  python -m pytest lms/djangoapps/grades/tests/ --ds=lms.envs.test -q
"
```

**前置条件**：Batch 1 依赖升级完成（celery 4.4 必须在 py38 容器中可 import）

**阻塞项**：celery 3.1 的 kombu.async → SyntaxError → 任何 `import celery` 都直接崩溃

**估时**：Batch 1 完成后 0.5 天

---

### M2 — Batch 1 依赖升级（让 Py3 runtime 能 boot）

> ⚠️ 2026-07-23：Python target 已改为 **3.6**。celery/kombu/edx-celeryutils **不需要升级**。

**做什么**：pymongo + mysqlclient 升级，修复 base.txt 打包问题，让 Py3.6 能 `pip install -e .`

```
mysqlclient 1.4.6           🟢 0.5d
pymongo 3.9.0               🟡 1d
python-memcached 1.59        🟢 0.5d
修复 git 包命名不匹配          🟢 0.5d  (edx-ora2/xblock-done/edx-sga)
beautifulsoup 升级            🟢 0.5d  (3.2.1 → 4.x)
                             ─────
                             ~2d
```

**阻塞项**：无（纯技术工作，不依赖 review）

**最佳时机**：现在 — 所有 open PR 在 review 中，这段时间可以做

---

### M3 — edx-celeryutils fork（解 celery 4.4 的最后阻塞）

**做什么**：fork `edx-celeryutils` 到 `Learningtribes/edx-celeryutils`：

1. `setup.py`：`celery>=3.1.25,<4.0` → `celery>=3.1.25,<5.0`
2. `LoggedPersistOnFailureTask`：`on_failure(self, exc, task_id, args, kwargs, einfo)` → celery 4.4 签名
3. `LoggedTask`：`after_return(self, status, retval, task_id, args, kwargs, einfo)` → celery 4.4 签名
4. `chord`/`chord_task`：验证 celery 4.4 兼容性

**估时**：1 天

---

### M4 — 「抄答案」流程化

**做什么**：在现代化 checklist 和 PR 模板中加"上游 ref"机制：

1. 对每个改动的模块，跑 `git log upstream/open-release/juniper.master -- <path>` 看有没有 Py3 相关 commit
2. 如有，在 PR body 中注明上游 ref
3. 高风险模式（csv、base64、iteritems bracket notation）强制要求对照

**估时**：0.5 天（流程文档化）

---

### M5 — CI DoD 升级（从「语法绿」到「Py3 测试绿」）

**做什么**：分阶段提升 CI 门禁：

| 阶段 | DoD | 说明 |
|:---:|------|------|
| 当前 | `py_compile` 语法绿 | ✅ 已达到 |
| 阶段 1 | `python3 -m pytest --collect-only` 收集绿 | 证明模块可被 pytest 发现 |
| 阶段 2 | `python3 -m pytest <module> -q` allow-fail | 建立 baseline，输出已知失败数 |
| 阶段 3 | 逐模块修到 0 失败 | 与上游 "drive failures to zero" 一致 |
| 阶段 4 | `python3 -m pytest <module>` = CI gate | Py3 测试失败 = build 失败 |

**当前阻塞**：阶段 2–4 全部依赖 M2（Batch 1 依赖升级）

---

## 优先执行顺序

```
现在（所有 PR 在 review，target = Python 3.6）
  │
  ├── M2: Batch 1 scoped 依赖升级（~2d）
  │     ├── 1. mysqlclient 1.4.6（立即可做）
  │     ├── 2. pymongo 3.9.0
  │     ├── 3. python-memcached 1.59
  │     ├── 4. 修复 git 包命名 + beautifulsoup 升级
  │     └── 5. py36-base.txt 生成
  │
  ├── M4: 流程文档化（0.5d）
  │
  └── Batch 1 完成后：
        │
        ├── M1: Py3 测试回路建立
        └── M5: CI DoD 升级

celery 3.1 + kombu 3.0 在 3.6 上可用 → 省掉 ~5-7 天
```

**M2 是当前唯一值得投入大块时间的方向** — 它解的是整个项目最后的技术阻塞。其他 PR 在 review、Phase 5 残量小、DCC 等人工 merge。依赖升级是唯一能做且做了就能解锁下一阶段的事情。

---

## 上游过渡期的关键数字参考

| 指标 | 上游 | 我们（当前） |
|------|:---:|:---:|
| 现代化代码在 Py2 上 bake | ~1 年 | 0-6 个月（最早 PRs 7 月开） |
| Dual-stack 测试时长 | 3.5 个月 | 0（未开始） |
| 从 dual-stack 到 Py3-only cutover | 1 天 | 待定 |
| 依赖升级范围 | pymongo 3.9 + mysqlclient + Django 2.2 | celery 4.4 + pymongo 3.9 + mysqlclient（Django 不动） |
| 双版本 CI 矩阵 | py{27,35,36,37}-django{111,20,21} | 无 Py3 CI |

**上游 3.5 个月 dual-stack + 1 天 cutover = 我们可以参考这个速度。前提是 Batch 1 先打通。**
