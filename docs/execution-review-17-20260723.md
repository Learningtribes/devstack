# Py3 迁移 — 执行审查第十七轮 (Execution Review 17)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 的 y1（python-modernize SyntaxError）+ y2（drf-nested-routers nested）
> 验证方法: collect --continue 全 error 捕获 + 按类型计数 + grep nested 源头 + 查 drf-nested-routers 导出
> 结论一句话: **✅ y1 modernize 生效（SyntaxError 138→74，collect 1931/768）；nested 63 仍未解，agent 未定位确切 import（在测试/vendored 非源码）。768 含 ~198 vendored deferred + ~570 真 fix。**

---

## 1. 验证证据

### ✅ y1 + collect 验证
- collect **1931/768**（agent 报一致，独立复现 24.37s）
- **SyntaxError 74**（138→74，−64）—— `python-modernize -wn` 生效（print/raise/except/octal/ur patterns 修 64）

### nested 63（agent 未解，溯源）
agent y2 "tried pin 0.90.2, still failing, renamed API" —— 实测 **63 `cannot import name 'nested'`**（handoff 准确；review-16 初版我误报 0，是 grep quoting artifact，撤回）。

溯源:
- grep `from X import nested` / `import nested` 在 **platform 源码 0 命中** → 63 nested error 在**测试文件或 vendored 包**，非平台源。
- `import rest_framework_nested.routers` 级联到 DRF 更深失败（traceback 截在 `rest_framework.serializers`）—— 可能 circular import 或 DRF 3.11 与 drf-nested-routers 0.90.2 某处不兼容。
- agent "renamed API" 但**未定位确切 import**。需 `grep -rn "import nested|from.*import.*nested" tests/ src/` 找确切调用点，看是 `from rest_framework_nested.routers import nested` 还是 `from rest_framework.routers import nested`（旧 DRF 符号），再决定 pin 哪个版本或写 shim。

## 2. 768 剩余构成（实测）

| 类别 | 数 | 性质 | 动作 |
|---|---|---|---|
| vendored src/ | 144 | 6F deferred（ORA2/xblockutils/codejail）| skip |
| `cannot import name 'nested'` | 63 | drf-nested-routers（在测试/vendored 非源码）| **定位 import + pin/shim** |
| SyntaxError | 74 | modernize 已降，剩边缘 case | 收尾 batch |
| urlparse/StringIO/HTMLParser | ~24 | Py2 import reorg | batch |
| tests.integration/unit | 33 | 测试包相对 import 结构 | 修包结构 |
| openassessment.* | ~38 | vendored ORA2（6F）| deferred |
| xblockutils | 16 | vendored（6F）| deferred |
| DjangoModelFactory | 8 | factory_boy 新版 API | 修 import |
| urlencode | 9 | urllib reorg | batch |

**deferred（6F）~198**（144 src + ~38 ORA2 + 16 xblockutils）。**真 fix ~570**（74 Syntax + 63 nested + ~33 import reorg + 33 结构 + 8 factory + rest）。

## 3. 裁决

| 项 | agent 自报 | 实测 | 裁决 |
|---|---|---|---|
| collect 1931/768 | 一致 | 复现 | ✅ |
| SyntaxError 74（−64）| y1 修 64 | 138→74 | ✅ modernize 生效 |
| nested 63 | still failing | 63，未解 | ⚠️ agent 未定位确切 import |
| nested 在源码? | "renamed API" | 源码 0 命中，在测试/vendored | ⚠️ agent 没找调用点 |

**agent 这轮诚实**（数字准），但 y2 nested 未解 + 未定位确切 import（只说"renamed API"笼统）。

---

## 4. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第十七轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-17-20260723.md
—— 先读 §1（nested 溯源）+ §2（768 构成）。

裁决速览（collect --continue 实测）:
- ✅ y1 modernize 生效: SyntaxError 138→74，collect 1931/768。
- ⚠️ nested 63 仍未解 —— 源码 0 命中，在测试/vendored，你上轮"renamed API"笼统没定位确切 import。
- 768 = ~198 vendored deferred（6F）+ ~570 真 fix。

下一阶段（768→低）:

z1. **定位 nested 的确切 import**（agent 上轮没做）:
   cd /edx/app/edxapp/edx-platform
   grep -rn "import nested\|from .* import .*nested\|from rest_framework_nested" tests/ src/ common/ lms/ cms/ openedx/ --include="*.py" | grep -i nested
   找 63 个 "cannot import name 'nested'" 的确切调用点（是 `from rest_framework_nested.routers import nested`？`from rest_framework.routers import nested`？还是别的）。
   定位后:
   - 若 `from rest_framework_nested.routers import nested` → drf-nested-routers 0.90.2 无 nested，找有 nested 的旧版 pin，或改用 NestedDefaultRouter/NestedSimpleRouter。
   - 若 `from rest_framework.routers import nested` → DRF 3.11 移除了（旧 DRF 符号），写 shim 或改 import。
   - 若在 vendored src/ → 6F deferred，skip。
   修后重跑 collect，63 应消。

z2. **收尾 SyntaxError 74**: modernize 边缘 case（modernize 没自动改的，手动）。重跑 collect。

z3. **batch import reorg ~24**（urlparse→urllib.parse, StringIO→io, HTMLParser→html.parser）+ **urlencode 9** → sed 批量。

z4. **factory_boy DjangoModelFactory 8 + tests.integration/unit 33**: 修 import（新版 API）+ 修测试包结构（__init__/conftest 让相对 import 过）。

z5. **vendored src/ ~198 skip**（6F deferred）: pytest norecursedirs src/ 或 conftest skip，不阻塞 platform 基线。ORA2 真解 z6。

z6. **ORA2/6F 真解（尾部风险）**: 6F ora2+proctoring ~70K SLOC 无上游 Py3 fork —— patch/wait/replace。唯一仍可能显著推后时间线。

collect 768→低（z1-z5）后 → tox py3 allow-fail baseline（Gap C / OEP-7 rung 2）→ 跑真测试记 failure 基线 → drive→0。

硬约束（不变，review-verdict §5）:
1. 共享 DB 安全: 真连 DB 用独立 py3 schema。
2. Py3 env 独立不动 Py2 devstack。
3. code fix 在 py36-boot-fixes 分支，commit+push。
4. **验证真跑（--continue collect + grep 定位 import），不只信"renamed API"笼统** —— 本轮抓 agent nested 未定位。
5. diff/版本自跑 git/pip 验证。
6. platform 其他分支不动（现 py36-boot-fixes）。

回报格式: 每步「做了什么 / 命令+真输出 / 判定 / 下一步」。先做 z1（grep 定位 nested 确切 import + 贴 grep 输出），定位后才能决定 pin/shim/改 import。
```
