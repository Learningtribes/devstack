# Py3 迁移 — 执行审查第十九轮 (Execution Review 19) — modernize 失误 + 恢复

> Date: 2026-07-24 · Reviewer: Claude (审查 agent)
> 性质: **自我失误记录 + 恢复**（非 agent 报告审查）
> 结论: 跑 `python-modernize -nw` 经 bind-mount 污染 host 178 文件 + 破坏 boot。方案 A 恢复（stash + 重应用 15 fix）。boot ✅，工作树干净，collect 回退待恢复。

---

## 1. 失误

为推进 711 failures（stacked-ism），跑了 `python-modernize -nw` 在容器源码想 broad batch 修。

**错在**:
- **容器 `/edx/app/edxapp/edx-platform` 是 host `platform/` 的 bind-mount** —— docker exec 的 modernize 直写 host 工作树（不是只改容器；docker cp 也冗余）。
- modernize **绝对→相对 import 转换**（48 处）与 manual boot fix 冲突:
  - `from calc.calc import *` → `from .calc.calc import *`（calc.calc 是模块非包 → ModuleNotFoundError）
  - `urllib` 等 → boot 多处崩
- 污染 178 文件（多无害 `from __future__ import absolute_import` 加法 + 48 危险 import 转换）。

## 2. 恢复（方案 A）

1. `git stash push -m "modernize-pollution-backup"` —— stash 全部未提交（agent 未提交 + 我 15 fix + modernize 污染），保全。
2. 工作树回 committed（967954f + cb1ef5b）→ **boot 恢复 "System check 0 issues"** ✅
3. 重新干净应用我 15 fix（body 级: basestring→str / sort key / .next / unicode / reduce / hashlib encode / reload import / dict.keys / tuple init），**无 import 转换**。
4. 验证: boot ✅，工作树 12 文件 modified，**无 modernize 污染残留**，15 fix 关键行在。

## 3. 当前状态

- ✅ **boot + check 0 issues**
- ✅ 工作树 = committed + 我 15 fix（干净，可 commit）
- ✅ nose shim 是 committed 的 → 保留（nose 错误 0）
- ⚠️ **collect 回退 613→794**（1684/794）—— uncommitted 的 collect 改进（urlparse batch / test modernize / vendored skip 配置）在 stash，工作树回退丢了它们
- ⚠️ run baseline 待重测（15 fix 在，但 collect 回退影响能跑的测试数）

## 4. stash（stash@{0}: modernize-pollution-backup）

- ✅ 好的: agent 未提交 collect 改进 + post-cb1ef5b source fix
- ❌ 坏的: modernize 178 文件污染
- 恢复选项: **重跑脚本化改进**（urlparse batch + test modernize + vendored skip，在干净状态上重跑，避开 modernize surgery）> cherry-pick stash

## 5. 教训（落盘，防再犯）

1. **`python-modernize -wn` 不可在 source 有 manual fix 时盲跑** —— absolute→relative import 转换与 manual boot fix（calc 等）冲突破坏 boot。scope: **test 文件 OK**（agent y1），**source 文件危险**。
2. **容器是 host bind-mount** —— docker exec 写操作直改 host，docker cp 冗余。改前先 `docker inspect ... --format '{{.Mounts}}'` 查 mount。
3. **broad batch 工具（modernize）在已手工修复的代码上 = 风险** —— 先确认 scope（test vs source）+ 不与 manual fix 冲突的子集。
4. **stacked-ism 现实**: 单根因 manual fix 到 diminishing returns（batch 3 −2 net），broad batch 是对的方向但**执行要安全**（test-only modernize / 精确 sed，非全树 modernize）。

## 6. 15 fix 清单（已干净重应用，可 commit）

| 文件 | fix | 类别 |
|---|---|---|
| capa/capa/util.py:104 | `sorted(cmp)` → `key=len, reverse=True` | sort key（−66）|
| chem/chemcalc.py:267 | `parsed.next()` → `next(parsed)` | generator（−54）|
| sandbox/draganddrop.py:104 | `(unicode,str)` → `str` | unicode（−49）|
| chem/miller.py | `from functools import reduce` | reduce（−28）|
| capa/capa_problem.py:925 | `basestring` → `str` | basestring（−71，stacked）|
| util/testing.py | `from importlib import reload` | reload（−21，stacked）|
| sandbox/draganddrop.py:356 | `dict.keys()[0]` → `list(...)` | dict_keys（−44，stacked）|
| grades/models.py:50 | tuple `__init__(blocks)` → `__init__()` | tuple init（−21，stacked）|
| track/middleware.py:185 | hashlib `.encode()` | hashlib |
| xmodule/static_content.py:92,140 | hashlib `.encode()` | hashlib |
| instructor_task/models.py:332 | hashlib `.encode()` | hashlib |
| badges/badgr.py:69,72 | hashlib `.encode()` | hashlib |
| badges/course_complete.py:34 | hashlib `.encode()` | hashlib |

批 1（前 4）实测 −87 failures（isolated single-cause）。批 3（basestring/reload/dict_keys/tuple）正确但 stacked（−2 net，测试进展撞下一 ism）。批 2（hashlib）proactive，0 measured（review-1 类，当前测试没 hit）。
