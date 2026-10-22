# Py3 迁移 — 执行审查第二十三轮 (Execution Review 23) — modernize 定论 + safe-regex

> Date: 2026-07-27 · Reviewer: Claude (审查 agent)
> 审查对象: modernize-source 第三次尝试 + broad safe-regex sweep（iteritems/ugettext）
> 结论: **modernize 对 source 不可用（3× 崩 boot），test-only 是唯一安全 scope。source 用 broad safe-regex + hand-Edit。**

---

## 1. modernize 三次实测定论

| # | 尝试 | 结果 |
|---|---|---|
| R19 | source 全 fixer | ❌ boot 崩（import absolute→relative 冲突 manual boot fix）|
| R20 | **test-only** | ✅ 安全 + 有效（+103 collected）|
| R23 | source 排除 import/imports_six | ❌ **仍崩**（urllib six fixer 改 import → `urllib not defined`）|

**定论: modernize-on-SOURCE 对这个 codebase 不可用** —— fixer 太多（import/imports_six/urllib_six/map/filter/metaclass/input_six/itertools_six...），逐个排除后 safe 子集太小不值，且持续与 manual boot fix 冲突。**test-only 是唯一安全 scope**（R20 已做）。

## 2. 正确 source 路径: broad safe-regex + hand-Edit

broad **safe regex**（方法/属性调用，AST-safe，不碰标识符）:
- ✅ `.iteritems()`/`.iterkeys()`/`.itervalues()` → `.items()`/`.keys()`/`.values()`（75 文件）
- ✅ `ugettext` → `gettext`（130 文件）
- → 合计 commit `73bc005`，**−42 failed**（broad 比 per-cluster ~−15 更有效）

**不能 broad**（需 hand-Edit per-file）:
- ❌ `unicode` → `str`: 撞 calc pyparsing grammar 标识符（`str` 冲突 pyparsing String 内建）
- ❌ `basestring` → `str`: 同 pyparsing 标识符冲突
- `print` 语句: 语法改，需 AST（modernize 的 `-p` 或手工）
- `cStringIO`/`StringIO` → `io`: BytesIO/StringIO 区分，需判断

## 3. 累积进度（R20 → R23）

| | R20 | R23 |
|---|---|---|
| failed | 637 | **508** |
| passed | 827 | **956** |
| boot | ✅ | ✅ |

**−129 failed, +129 passed。956 测试过**（逼近 1000）。

## 4. 教训（落盘）
1. **modernize 绝不跑 source**（3× 崩 boot）。test-only OK（R20）。
2. **broad regex 只对方法/属性调用安全**（`.iteritems()`/`ugettext`）—— AST 区分 builtin vs 标识符靠不住 regex，`unicode`/`basestring` 必 hand-Edit。
3. broad safe-regex（−42）比 per-cluster（~−15）更有效 —— 优先 broad-safe，再 per-file 收尾。

## 5. py36-boot-fixes（12 commit，全 pushed）
boot-fix(2) + 15-systematic + stdlib-reorg + nested-polyfill + test-modernize + hmac/bytes + .claude-清理 + 6-fix + iteritems/ugettext-sweep。
