# Py3 迁移 — 执行审查第十五轮 (Execution Review 15)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 的 w1（823 collection error 分类）
> 验证方法: collect --continue 全 error 捕获 + 按错误类型/缺失模块分类计数
> 结论一句话: **✅ 分类大体准确（823 主要 env setup 非 Py3 不兼容，de-risk）；但 nose（198）是迁移非 pip 装，别低估。**

---

## 1. 验证证据（collect --continue 全 823 error 实际捕获）

按错误类型:
- ModuleNotFoundError: **644**
- ImportError（含上）: 763
- SyntaxError（Py2 语法）: 87

缺失模块 top:
| 模块 | 命中 | 性质 |
|---|---|---|
| `factory` | 205 | factory_boy —— **pip 可装** ✅ |
| `nose` | 198 | ⚠️ **迁移非 pip 装**（见 §2）|
| `freezegun` | 32 | pip 可装 ✅ |
| `bok_choy` | 23 | pip 可装 ✅ |
| `tests.integration`/`tests.unit` | 33 | 测试包相对 import 结构问题（非 pip）|
| `openassessment.*` | ~38 | vendored ORA2 测试（6F deferred）|
| `httpretty` | 16 | pip 可装 ✅ |
| `xblockutils` | 15 | vendored（6F）|
| `urlparse`/`StringIO` | 16 | Py2-ism（真 fix）|
| `lettuce` | 9 | 旧 BDD 框架（可能可移除）|

agent "~500 pip 可装 + ~150 vendored + ~130 Py2 fix" reframe **大体准确** —— 823 多是 env setup 非 Py3 不兼容，**de-risk 大**。

## 2. ⚠️ 关键 nuance: nose（198）是迁移非 pip 装

agent 把 nose 归"pip install needed"，但 **nose 是 Py2-era runner，Py3 支持差/官方弃用**，Py3.6 上装了也运行不可靠。198 个测试 `import nose`（`from nose.plugins.attrib import attr` / `nose.SkipTest` / `nose.tools` 等）。

→ 修法非"pip install nose"，而是:
- **装 nose**（Py3.6 不可靠，不推荐）
- **或 nose→pytest 迁移**: platform setup.cfg 已是 pytest，conftest 已提供 @attr 分片 shim（CLAUDE.md 提及）。改测试的 nose import 为 pytest 等效（`@pytest.mark...` / `unittest.SkipTest` / pytest tools），或写 nose compat shim 模块。

→ "~500 pip 可装"中 **~198 nose 实为迁移工作**。修正分类:
- ~300 简单 pip 装（factory_boy/freezegun/bok_choy/httpretty）
- **~198 nose→pytest 迁移（真工作块）**
- ~150 vendored ORA2/xblockutils 测试（6F deferred）
- ~130 真 Py2 fix（urlparse/StringIO/SyntaxError，多已做）

仍比"823 Py2-ism"吓人程度低得多，但 nose 迁移是 hidden work，agent 低估。

## 3. 裁决

| 项 | agent 自报 | 实测 | 裁决 |
|---|---|---|---|
| 823 分类 | ~500 pip + ~150 vendored + ~130 Py2 | 大体一致 | ✅ reframe 准确 |
| "pip 可装"含 nose | nose 归 pip | nose 是迁移非装 | ⚠️ 低估 |
| de-risk 823 | 主要 env setup | 实测坐实 | ✅ |

**agent 这轮诚实**（分类与实测大体一致），唯一漏: nose 性质（迁移 vs 装）。

---

## 4. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第十五轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-15-20260723.md
—— 先读 §2（nose 迁移 nuance）。

裁决速览（collect --continue 实测）:
- ✅ 823 分类大体准确: ~500 缺包 + ~150 vendored + ~130 Py2-ism。823 多是 env setup 非 Py3 不兼容，de-risk 大。
- ⚠️ nose（198）是迁移非 pip 装 —— Py3 nose 不可靠，需 nose→pytest 迁移或 shim。agent 上轮低估。

下一阶段（823→0，修正）:

x1. **pip 装真可装的测试依赖**（~300，琐碎）:
   pip install factory_boy freezegun bok_choy httpretty（以及 collect 暴露的其他纯 pip 缺包）
   装后重跑 --continue collect，823 应骤降（~300 消）。记新基线。

x2. **nose→pytest 迁移**（~198，真工作块）:
   - 评估范围: grep `from nose` / `import nose` / `nose.plugins` / `nose.SkipTest` / `nose.tools` 在测试代码
   - 决策: (a) 写 nose compat shim 模块（最小改动，让 import 过 + 行为映射 pytest）或 (b) 改测试 import 为 pytest 等效（更干净但量大）
   - 优先试 shim（快），collect 过后再逐个改真 import
   - 注意 @attr 分片: conftest 已有 shim（CLAUDE.md），确认覆盖

x3. **vendored 测试 skip**（~150，6F deferred）:
   src/xblock-utils, ora2 等 vendored XBlock 测试 —— pytest 配置 norecursedirs 或 conftest skip，不阻塞 platform 测试基线。ORA2 真解在 x5。

x4. **剩余 Py2-ism batch fix**（~130）: urlparse/StringIO/SyntaxError(print/except) —— python-modernize/sed 批量。多已做，收尾。

x5. **ORA2/6F 真解**（prod-gate，尾部风险）: openassessment vendored 测试 + GRADABLE_BLOCKS 运行时 XBlock。6F ora2+proctoring ~70K SLOC 无上游 Py3 fork —— patch/wait/replace 决策。唯一仍可能显著推后时间线的尾部风险。

collect 823→低（x1+x2+x3+x4）后 → tox py3 allow-fail baseline（Gap C / OEP-7 rung 2）→ 跑真测试记 failure 基线 → drive failure→0。

硬约束（不变，review-verdict §5）:
1. 共享 DB 安全: 真连 DB 用独立 py3 schema。
2. Py3 env 独立不动 Py2 devstack。
3. code fix 在 py36-boot-fixes 分支，commit+push。
4. **验证真跑（--continue collect + 分类计数），不只信数字** —— 本会话活测贯穿，本轮抓 nose 性质低估。
5. diff/版本自跑 git/pip 验证。
6. platform 其他分支不动（现 py36-boot-fixes）。

回报格式: 每步「做了什么 / 命令+真输出 / 判定 / 下一步」。先做 x1（pip 装真可装依赖 + 重跑 collect 记新基线），823 应骤降。再 x2（nose 迁移评估 + shim）。
```
