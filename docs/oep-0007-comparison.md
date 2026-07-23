# OEP-0007 vs Hawthorn 迁移 — 整体评估

> Date: 2026-07-23 · 自包含版本，不引用外部文件路径
> Status：OEP-7 = Obsolete（上游已完成全平台 Py3），本文对照上游方案评估我们的推进状态

---

## 1. 上游用了多久？

OEP-7 起草于 2016-08-12，上游 Open edX 在 **Juniper 发布（2020-06）** 完成 Py3 迁移，edx-platform 实际迁移约 **15 个月**。

| 里程碑 | 时间 | 说明 |
|------|------|------|
| OEP-0007 起草 | 2016-08 | 官方 Py3 迁移最佳实践 |
| Python 2 EOL | 2020-01 | 硬 deadline |
| Hawthorn 发布 | 2018-08 | Python 2.7, Django 1.11 |
| Juniper 发布 | 2020-06 | **第一个 Py3 release**（Django 2.2） |
| OEP 标记 Obsolete | 2021+ | 全平台 Python ≥ 3.8 |

上游有专职团队 + 社区，同步升级了 Django 2.2 + Celery/ES/MongoDB 全栈。

---

## 2. OEP-7 是一种「标准答案」而非探索蓝图

OEP-7 是 edX 在 **首次探索** Py3 迁移时的记录——它必须保证发现顺序安全（deps 先于 code，xblock 先于 platform）。上游已经走通了这条路，我们不需要重复发现过程：

| OEP-7 内容 | 对我们是否约束 | 原因 |
|------|:---:|------|
| **方法**：six + `__future__` + unicode sandwich + 测试驱动阶梯 | ✅ 仍约束 | 语言级真理，不因谁执行而改变 |
| **顺序**：deps-before-code, xblock-remote-execution-first | ⚠️ 大部放宽 | 上游已走过→答案已知。我们站在答案之上，不需要保护发现顺序 |

**我们的立场**：
1. 顺序不神圣——因为标准答案存在
2. 真正约束是**可记录+可验证**——每步在 Py2 分支上双兼容、上线、bake，切之前可审计
3. **抄答案**——上游有 Py3 commit 的文件，直接挖掘其 diff 意图，而非从头推导

---

## 3. 方法一致性矩阵

| OEP-7 原则 | 我们 | 判定 |
|------|------|:---:|
| six + `__future__` 单代码库双兼容 | `unicode()→text_type()`, `iteritems→six.iteritems`, `basestring→string_types`, `except E,e→as`, `print→print()` 全覆盖 | ✅ |
| python-modernize 自动化 | 批量 modernize + 手动修复正则 bug（self.six, bracket notation, method chain） | ✅ |
| 部署目标 = 单一版本（Py3.8） | 目标 3.8，保持 2.7 双兼容直到 cutover | ✅ |
| 禁止 blanket `unicode_literals` | 主动移除，使用 OEP-7 Option 2（显式 u''/b'' 字面量） | ✅ 独立得出与官方相同的谨慎结论 |
| `six.PY2` 而非 `six.PY3` | 文档规范，review 时 check | 🟢 |
| `six.moves` / stdlib 重命名 | 全面应用 | ✅ |
| **测试驱动阶梯** | CI 仅 `py_compile` 语法检查；`paver test_lib` 在 py38 上是手动的，非门禁 | 🔴 **唯一真方法差距** |
| caniusepython3 pylint 指标 | 用 `py_compile` 替代 | ⚠️ 代理指标 |

---

## 4. `unicode_literals` 偏离（独立得出与 OEP-7 相同的结论）

OEP-7 对 `unicode_literals` 的官方警告（§Text handling, Option 1）：

> "requires changing code one full file at a time... it creates non-local semantics for text and byte literals"

我们实际遭遇的问题完全印证了这段警告：
- 11 个测试因 tuple `repr()` 带 `u''` 前缀断裂
- Django 1.11 部分路径期望 `str`（bytes），unicode → `UnicodeEncodeError`
- 主动移除并采用 OEP-7 Option 2（显式字面量）——与官方备选方案一致

---

## 5. `six.iteritems()` vs `six.viewitems()`（等价选择）

| | `six.iteritems(d)` | `six.viewitems(d)` |
|------|------|------|
| Py2 行为 | `dict.iteritems()` — iterator | `dict.viewitems()` — view |
| Py3 行为 | `dict.items()` — view | `dict.items()` — view |
| **Py3 等价** | ✅ | ✅ |

两者在 Py3 完全等价。我们选择 `iteritems` 因为代码中本身就用 `.iteritems()` 模式，保持语义连贯。

---

## 6. Gap 重新定级（"抄答案"框架下）

在"上游已走通 → 答案已知"的框架下，三个原 OEP-7 约束 Gap 重新评估：

### 🟡 Gap A — deps-before-code 顺序（从 🔴 降级到 🟡，非 🟢）

OEP-7 line 143-145 要求先确保依赖支持 Py3 再转代码（"Before converting a codebase to Python 3, we need to make sure the code we depend on will also support Python 3"）—— 这是 **runtime 前置条件**，不是 discovery-order 便利。我们做了 code-first；celery/driver Batch-1 未启动，所以 Py3 运行时目前无法 boot。

- **为什么可从 🔴 降到 🟡（而非 🟢）**：答案已知 → 目标依赖集已确定（celery 4.4, pymongo 3.9, mysqlclient 1.4.6, mongoengine 0.10.0, memcached 1.59; redis 解耦 — broker=amqp）→ **无发现/探索风险**，故可降级。但 deps 仍是 **functional blocker**（runtime 不能 boot）—— "答案已知"不能让 runtime 启动，故不能降到 🟢。
- **残余关注**：deps 仍是验证回路（Gap C）的硬门。Gap A 的 🟡 severity 与此一致；原 🟢 与"runtime can't boot"自相矛盾。

### 🟢 Gap B — xblock/ora2 先迁移（从 🟡 降级）

OEP-7 要 xblock-remote-execution/bicompat window 先做。我们推迟 6F（vendored `src/`）。

- **为什么可以接受**：remote xblock execution 是 edX 服务多运营商的生态顾虑，对单 LT 部署基本无意义。
- **残余关注（保持实在）**：`edx-ora2` + `edx-proctoring` 是硬生产依赖（`ENABLE_SPECIAL_EXAMS=True`），LT fork，**无上游 Py3 fork**——经典 OEP-7 "lib 不支持 Py3 → patch/wait/replace" 场景。保持为独立追踪项。

### 🔴 Gap C — 语法验证 vs 测试驱动（唯一幸存，最高优先级）

这是直接违背我们自身"可验证"立场的差距。OEP-7 整个"项目迁移"阶梯是测试驱动的；我们的门禁是 `py_compile`。

- **后果**：语法绿 → Py3 测试绿 之间的 delta 正是 OEP-7 说真正工作量所在（文本处理/unicode sandwich/依赖行为）。我们当前指标**看不到**这个 backlog。
- **这是唯一在"抄答案"框架下仍存活的差距**，因为它是验证性差距，不是顺序性差距。

---

## 7. 「抄答案」策略

上游 Open edX 迁移了每个我们 touch 的文件 → 把其 Py3 diff 当成 oracle。

### 挖掘什么
- 对我们正在现代化的文件，找上游 Py3 时代的版本，diff 意图（非逐字——我们的树有 LT fork 差异）
- 高价值目标：`iteritems`/`viewitems` 语义、csv/base64 bytes-vs-str 边界、`six.reraise`、`__hash__`/ordering、`sort`/`cmp` 移除、dict-order 假设

### 安全使用
1. **方法而非补丁**：复制上游对某构造的处理方式，在我们的 Py2/Py3 双兼容约束下重新应用
2. **绝不 whole-file checkout**：手挑 hunk
3. **记录出处**：PR body 中注明上游 ref，满足可记录性约束，加快 review

### 不适用场景
- LT-fork XBlocks + ora2/proctoring：上游分支不同，上游 Py3 工作可能不映射——需原始评估
- 上游已删但我们保留的（或反之）——DCC 移除集

---

## 8. 我们做得比 OEP-7 更好的地方

1. **Bridge-version 依赖策略**：把 six 的双兼容单代码库思想应用到依赖层——每个 driver 升级到 Py2/3 双兼容 bridge 版本，在 Py2 生产上 bake 后再切。OEP-7 只说"先检查 deps"；这个分阶段 bake playbook 是真正的增强。

2. **Review 吞吐治理**：OEP-7 假设 edX 级别的 review 容量。我们测量了 review——不是 dev——是约束条件（Phase 4 级别 ~0.17 PR/wk）。与 OEP-7 正交，正确的本地补充。

---

## 9. 建议（对齐「抄答案」立场）

1. **关闭 Gap C —— 建立 Py3.8 测试回路作为 DoD（最高杠杆）**：用已有 py38 容器跑 `paver test_lib` / 定向 `test_system` 在 allow-fail baseline 模式，把不可见的 Py3 测试 backlog 转成可度量数字。推送 CI DoD 从"语法绿"向"Py3 测试绿"。按三种 DoD 状态报告（语法绿 / Py3 测试绿 / 生产验证）。

2. **celery 4.4 + driver Batch-1 上关键路径**：不是因为 OEP-7 顺序要求，而是它是**任何 Py3 测试回路的前提**。只有 runtime 能 boot，allow-fail 才能转为 real-green。

3. **落实「抄答案」**：现代化 checklist 中加"上游 ref"行；PR 模板加字段；对 §7 中列出的高错误率构造优先挖掘上游。

4. **保持 ora2/proctoring 为独立追踪项（Gap B 残余）**：启动 patch-or-replace 评估，不让顺序降级掩盖。

---

## 10. 一句话投影

**我们的「怎么改代码」已经 OEP-7 一致——且在依赖层更强。唯一幸存差距是「怎么验证」——OEP-7 是测试驱动，我们是语法驱动。由于我们自己定的最高优先级正是可记录+可验证，关闭 Py3 测试回路（Rec 1）、以依赖 Batch-1 为门（Rec 2）、用抄上游答案加速（Rec 3），就是「看起来完成」到「OEP-7 标准完成」的路径。**
