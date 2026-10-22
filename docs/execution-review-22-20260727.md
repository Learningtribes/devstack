# Py3 迁移 — 执行审查第二十二轮 (Execution Review 22)

> Date: 2026-07-27 · Reviewer: Claude (审查 agent)
> 审查对象: hmac/bytes fix + 6 systematic root cause batch（ugettext/reduce/iteritems/dict.keys/unicode）
> 验证方法: docker exec 真跑 pytest baseline + git 验 commit
> 结论: ✅ 累积 −87 failures（637→550 failed，827→914 passed）。stacking 现实: per-cluster batch ~−15 net 稳态。

---

## 1. 进展

| commit | 内容 | 效果 |
|---|---|---|
| `0ef4ffa` | hmac/bytes（track:186 session_key / pipeline:501 unicode+510 data_str / ssencrypt:171 message + :172 rstrip b'\n'）| 含发现 pipeline:501 `unicode` Py2-only NameError（隐藏崩点）|
| `c20a8fb` | 6 systematic（responsetypes ugettext ×24 / request_cache reduce / calc iteritems / draganddrop dict.keys ×2 / block_structure unicode / waffle_utils unicode）| −15 net |

## 2. baseline 演化（R20 → R22）

| | R20 | R22 |
|---|---|---|
| failed | 637 | **550** |
| passed | 827 | **914** |
| collect errors | 626 | 626（stuck）|
| boot | ✅ | ✅ |

**+87 测试过**（实打实）。914 passed 地基。

## 3. ⚠️ stacking 现实（关键判断）

每 batch 修根因（正确，warnings↑ 827→841 证测试跑更远）但 **net ~−15/batch 稳态**。原因: 测试调用链叠多个 Py2-ism，修一个进展撞下一个，仍 fail。626 collect errors stuck（那些测试根本跑不到，不计入 run）。

→ **per-cluster batch 到低 ROI 稳态**。更高效: **更宽 batch**（全平台 sweep 同类 Py2-ism，一次扫全，让 stacked 测试整链通过）或 per-test 链修。

## 4. 下一步策略（broad sweep）

targeted python sweep（**非 modernize**，避免 R19 source import 转换风险）全平台 common/lms/cms/openedx（排除 src/）:
- `.iteritems()` / `.iterkeys()` / `.itervalues()` → `.items()` / `.keys()` / `.values()`
- `unicode(` → `str(`
- `basestring` → `str`
- `.ugettext` → `.gettext`（+ ugettext_lazy 等）

每改验 boot（source 改动，必验）+ 量 baseline。这些是 body 级替换，无 import 转换，安全。

## 5. py36-boot-fixes（11 commit，全 pushed）
boot fix(2) + 15 systematic + stdlib reorg + nested polyfill + test-only modernize + hmac/bytes + .claude 清理 + 6-fix batch。
