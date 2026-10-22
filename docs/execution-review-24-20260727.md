# Py3 迁移 — 执行审查第二十四轮 (Execution Review 24)

> Date: 2026-07-27 · Reviewer: Claude (审查 agent)
> 审查对象: broad safe-regex 收尾（func_X sweep）+ 累积总结
> 结论: ✅ broad-safe regex 模式耗尽（iteritems/ugettext/func_X 全扫），**971 passed**。剩余 per-file 长磨。

---

## 1. 本轮

| commit | 内容 | 效果 |
|---|---|---|
| `9806acd` | 6 root cause（draganddrop dict.keys ×2 / request_cache func_name / grades unicode ×2 / inputtypes import six）| −12 net |
| `9ee242b` | broad sweep `.func_X` → `.__X__`（4 文件，多数已修）| −3 net |

## 2. 累积进度（R20 → R24）

| | R20 | R24 |
|---|---|---|
| failed | 637 | **493** |
| passed | 827 | **971** |
| boot | ✅ | ✅ |

**−144 failed, +144 passed。971 测试过**（R1 零运行时 → 971）。

## 3. broad-safe regex 已耗尽

done（安全 + 有效）:
- `.iteritems()`/`.iterkeys()`/`.itervalues()` → items/keys/values（大）
- `ugettext` → `gettext`（大）
- `.func_X` → `.__X__`（小）

**不能 broad**（需 per-file hand-Edit，R22/R23 教训）:
- `unicode`/`basestring` → `str`: 撞 calc pyparsing grammar 标识符（`str` 冲突 pyparsing String）。**逐文件**（非 calc 文件安全）。
- `print` 语句: 语法改，需 AST（modernize `-p` 或手工）。
- `cStringIO`/`StringIO` → `io`: BytesIO/StringIO 区分，逐文件判断。
- `modernize-on-source`: 3× 证伪（R19/R23），绝不用。

## 4. py36-boot-fixes（14 commit，全 pushed）
boot-fix(2) + 15-systematic + stdlib-reorg + nested-polyfill + test-modernize + hmac/bytes + .claude-清理 + 6-fix + iteritems/ugettext-sweep + 6-rootcause + func_X-sweep。

## 5. 下一步路径（per-file 长磨）
剩 493 run failures + 626 collect errors:
- per-file `unicode`/`basestring`（非 calc 文件 hand-Edit）
- `print` 语句（AST 或手工）
- `cStringIO`/`StringIO`（io 转换）
- 626 collect errors（cStringIO/结构/provider 第三方）
- agent sustained drive（handoff-prompt-20260724.md 就绪）+ prod-gate/ORA2 决策（用户）

broad 工具红利结束，进入 per-file/per-test-chain 精修阶段。
