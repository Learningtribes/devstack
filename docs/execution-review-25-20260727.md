# Py3 迁移 — 执行审查第二十五轮 (Execution Review 25) — 🏁 1384 passed + modernize 单 fixer 突破

> Date: 2026-07-27 · Reviewer: Claude (审查 agent)
> 审查对象: store_utilities 级联解锁 + modernize 单 fixer（basestring/long/reduce）+ unicode regex
> 结论: ✅ **1384 passed**（R20 827 → +557）。modernize **单 fixer（`-f X`，排除 import 类）是 source 安全 broad 自动化的正解**。

---

## 1. 里程碑: 1384 passed

| | R20 | R25 | Δ |
|---|---|---|---|
| failed | 637 | 771 | +134（级联新暴露，可操作）|
| passed | 827 | **1384** | **+557** |
| errors | 626 | 588 | −38 |
| run 时长 | ~70s | 512s | suite 大涨（更多测试跑）|

**+557 测试过**（R1 零运行时 → 1384）。failed 涨是级联暴露的 runnable failures（非 import 阻塞，可 drive）。

## 2. 关键突破: modernize 单 fixer（source 安全）

R19/R23 modernize full/default 崩 boot（import 转换）。**本轮发现: 单 fixer（`-f X`）AST 安全**:
- `-f basestring` → six.string_types（34 文件，AST 不碰 pyparsing grammar name）
- `-f long` → long 字面量/builtin（11 文件）
- `-f reduce` → functools.reduce import
- 全 boot ✅

**+ unicode→six.text_type regex（296 文件，单独安全）** —— R22 break 是 basestring→str 混入非 unicode；unicode 不作 pyparsing grammar 标识符，regex 安全。

**定论修正（review-23）**: modernize 对 source **不是完全不可用** —— **单 fixer（排除 import/imports_six/urllib_six/map/filter/metaclass 等转换类）AST 安全**。full/default 才崩。这是 broad 自动化的正解。

## 3. store_utilities 级联解锁（高杠杆）

modulestore/store_utilities.py:56 `ur''` SyntaxError 阻塞广泛-import 模块 → 修了它（ur→r + unicode→str）解锁级联，**+381 passed 涌现**。教训: **广泛-import 核心模块的 Py2 SyntaxError 是高杠杆点**，优先于 per-cluster attr-error。

## 4. 本会话直接 fix 累积（R20→R25，py36-boot-fixes 18 commit）
- 15 systematic + stdlib reorg + nested polyfill
- test-only modernize（666 文件）
- hmac/bytes + .claude 清理
- iteritems/ugettext/func_X broad safe-regex
- store_utilities 级联解锁 + print + map→list(map)
- **modernize 单 fixer**（basestring/long/reduce）+ unicode regex

全 boot-verified。passed 827→**1384**（+557）。

## 5. 交接（1384 强交接点）

- py36-boot-fixes **18 commit**（origin 有 17，long/reduce 1 commit 本地待 push —— push auth 暂失败，用户 `git push origin py36-boot-fixes`）
- boot ✅ 0 issues，工作树干净
- **1384 passed** 地基稳，771 failed = drive-to-zero 队列，588 collection errors
- 剩余: agent sustained drive（`--tb=line` re-cluster post-cascade landscape）+ prod-gate/ORA2 用户决策

## 6. 教训汇总（本会话）
1. modernize **单 fixer（`-f X`，排除转换类）source 安全**；full/default 崩 boot。
2. **广泛-import 核心模块的 SyntaxError = 高杠杆**（修一个解锁几百测试）。
3. unicode regex **单独安全**（不作 pyparsing grammar 标识符）；basestring 必 AST（-f）。
4. 容器 = host bind-mount（docker exec 直改 host）。
5. `git add` 按路径（防 .claude 污染）；.gitignore 排除 .claude/。
6. 活测兜底贯穿（boot 验证每改）。
