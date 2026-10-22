# Py3 迁移 — 执行审查第十六轮 (Execution Review 16)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 的 x1/x2（pip deps + nose shim + urlparse fix，823→784）
> 验证方法: collect --continue 全 error 捕获 + 按错误类型/缺失模块/import 消息分类 + 查 nested 源头
> 结论一句话: **✅ 1707/784 + nose/factory 消除（agent 诚实）；DRF nested 59 = drf-nested-routers 包版本（非 core DRF，de-escalate）；但 SyntaxError 138 agent 低估（~40→138），真剩余 ~235 fix + 144 vendored deferred。**

---

## 1. 验证证据

### ✅ 1707/784 独立复现
`1707 tests collected, 784 errors in 30.02s`（agent 报一致）。nose/factory/freezegun ModuleNotFoundError 全 0（deps + nose shim 起效）。

### 784 实测构成（比 agent 细）
| 类别 | 数 | 性质 | 动作 |
|---|---|---|---|
| vendored src/ | ~144 | 6F deferred（ORA2/xblockutils/codejail）| skip |
| `cannot import name 'nested'` | 59 | **drf-nested-routers 包版本**（非 core DRF）| pin 正确版本/修 import |
| SyntaxError | 138 | Py2 测试语法: 66 print + 60 invalid-syntax + 12 invalid-token | batch-fix |
| urlparse/urlencode/StringIO/HTMLParser | ~30 | Py2 import reorg | batch-fix |
| DjangoModelFactory | 8 | factory_boy 新版 API compat | 修 import |
| tests.integration/unit | 33 | 测试包相对 import 结构 | 修包结构 |

### DRF nested de-escalate
agent 报"~50 DRF nested (DRF 3.11 compat)"。实测 **59 `cannot import name 'nested'`**，源头 `from rest_framework_nested import ...` → **drf-nested-routers 包**（`rest_framework_nested` 包装了但无 `nested` 符号），**非 core DRF 3.11 丢符号**。

→ keep-DRF-3.11.2 决策（review-14）**不受影响**。fix: pin 正确 drf-nested-routers 版本 或 修 import。de-escalate。

## 2. 裁决

| 项 | agent 自报 | 实测 | 裁决 |
|---|---|---|---|
| 1707/784 | 一致 | 复现 | ✅ |
| nose/factory 消除 | 是 | 0 | ✅ |
| DRF nested ~50 | DRF 3.11 compat | drf-nested-routers 包版本 | ✅ 数对，性质 de-escalate |
| SyntaxError | ~40 print | 138（66 print+60+12）| ⚠️ **低估** |
| vendored ~150 | 是 | 144 | ✅ |

**agent 这轮大体诚实**，唯一漏: SyntaxError 低估（~40→138）。真剩余 Py3 工作比 agent "~130 fix" 大: 138 Syntax + ~30 import reorg + 59 nested + 8 factory = **~235 真 fix + 144 vendored deferred**。

## 3. 净进展

823→784（−39），但 collected **1181→1707（+526）**。error **组成变了**:
- 缺模块 ↓474（deps + nose shim 消）
- 新发现测试带来 SyntaxError ↑51（87→138）+ nested 59 + factory_boy API 8

真正剩余 Py3 工作比"823"看着小，但比 agent "~130" 大（~235）。仍以 batch-fix 为主。

---

## 4. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第十六轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-16-20260723.md
—— 先读 §1（784 构成 + nested de-escalate + SyntaxError 低估）。

裁决速览（collect --continue 实测）:
- ✅ 1707/784 + nose/factory 消除 —— agent 这轮诚实。
- ✅ DRF nested 59 = drf-nested-routers 包版本（非 core DRF，keep-3.11.2 不受影响）。
- ⚠️ SyntaxError 138 agent 低估（~40→138）: 66 print + 60 invalid-syntax + 12 invalid-token。真剩余 ~235 fix + 144 vendored deferred。

下一阶段（784→低）:

y1. **batch-fix SyntaxError 138**（Py2 测试语法，最大块）:
   - 66 `print x` → `print(x)`: python-modernize 或 sed 批量
   - 60 invalid-syntax: raise E,V,T → six.reraise; except E,e: → as; exec code in g → exec(code, g)
   - 12 invalid-token: Py2 八进制 0775→0o775; ur""→r""; 0L long→0
   跑 python-modernize -wn tests/ 批量，再重跑 collect 记新基线。

y2. **fix drf-nested-routers nested (59)**:
   查 `from rest_framework_nested import nested` 的调用点 → pin 正确 drf-nested-routers 版本（提供 nested 符号）或 修 import 为该包实际导出的（NestedDefaultRouter 等）。重跑 collect，59 应消。

y3. **batch-fix import reorg ~30**: urlparse→urllib.parse, urlencode, StringIO→io, HTMLParser→html.parser。sed 批量。

y4. **factory_boy DjangoModelFactory (8)** + **tests.integration/unit 相对 import (33)**: 修 import（新版 factory_boy API）+ 修测试包结构（__init__/conftest）。

y5. **vendored src/ ~144 skip**（6F deferred）: pytest norecursedirs 或 conftest skip src/ 测试，不阻塞 platform 基线。ORA2 真解 y6。

y6. **ORA2/6F 真解（尾部风险）**: openassessment vendored 测试 + GRADABLE_BLOCKS 运行时 XBlock。6F ora2+proctoring ~70K SLOC 无上游 Py3 fork —— patch/wait/replace。唯一仍可能显著推后时间线。

collect 784→低（y1-y5）后 → tox py3 allow-fail baseline（Gap C / OEP-7 rung 2）→ 跑真测试记 failure 基线 → drive→0。

硬约束（不变，review-verdict §5）:
1. 共享 DB 安全: 真连 DB 用独立 py3 schema。
2. Py3 env 独立不动 Py2 devstack。
3. code fix 在 py36-boot-fixes 分支，commit+push。batch-fix 用 python-modernize（-wn 写回），先 git 确认 diff 再 commit。
4. **验证真跑（--continue collect + 分类计数），不只信数字/自报** —— 本轮抓 SyntaxError 低估（138 vs ~40）。
5. diff/版本自跑 git/pip 验证。
6. platform 其他分支不动（现 py36-boot-fixes）。

回报格式: 每步「做了什么 / 命令+真输出 / 判定 / 下一步」。先做 y1（python-modernize batch-fix SyntaxError 138 + 重跑 collect 记新基线），138 是最大块。
```
