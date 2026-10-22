# Py3 迁移 — 执行审查第十四轮 (Execution Review 14)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 的 v1/v2/v3（DRF constraint + 决策 + collect 基线复现）
> 验证方法: docker exec 验 constraint 7 pin + branch + boot + pytest --continue collect
> 结论一句话: **✅ 全清洁轮（首个无 over-reporting 轮）。constraint 7 pin + boot + 1181/823 collect 基线全独立复现。Gap C 工作队列确认。**

---

## 1. 验证证据（全实测）

### ✅ constraint 7 pin（DRF 锁住）
```
Django==1.11.29
celery==3.1.25
kombu==3.0.37
pymongo==3.9.0
mysqlclient==1.4.6
mongoengine==0.10.0
djangorestframework==3.11.2
```
DRF 不再漂移（review-13 silent-upgrade 风险收口）。

### ✅ platform 回 py36-boot-fixes + boot 仍行
- branch: `py36-boot-fixes`（`cb1ef5b1969`）
- `call_command("check")` → "System check identified no issues (0 silenced)" ✅

### ✅ collect 1181/823 独立复现
```
DJANGO_SETTINGS_MODULE=lms.envs.test python -m pytest --collect-only --continue-on-collection-errors -q
→ 1181 tests collected, 823 errors in 19.81s
```
agent 报 18.92s，数字 1181/823 逐字一致。**本轮首次完全复现 agent 报告，无 over-reporting。**

## 2. v2 DRF 决策合理

**keep 3.11.2** —— 理由: Juniper 用 **vanilla DRF 3.9.4**（非 edx fork），Hawthorn 的 edx fork patch 已 upstreamed/dropped。3.11.2 过 boot+check+basename。论据 sound（参照 Juniper 这个 Py3 参考实现）。

edx fork @1ceda7c 的 patch 若 Juniper 已吸收，vanilla 3.11.2 安全。constraint pin `djangorestframework==3.11.2` 防再漂移。

## 3. 823 collect error 观察

样本: `ERROR src/xblock-utils/tests/unit/test_settings.py` —— 部分 823 是 **vendored XBlock 测试**（src/ 下）的 collection error，连 6F。

→ 823 不全是 platform 代码 Py2-ism，有 **6F vendored 测试成分**。drive-to-zero 时需区分:
- **platform 代码 Py2-ism**（urlparse/iteritems/except-E,e/import-absolute 等）→ 平台 fix
- **vendored XBlock 测试**（src/xblock-utils, ora2, etc.）→ fork patch，不平台改

## 4. 裁决

| 项 | agent 自报 | 实测 | 裁决 |
|---|---|---|---|
| v1 constraint 7 pin | DRF 加 | 7 pin 含 DRF==3.11.2 | ✅ |
| v2 keep 3.11.2 | Juniper vanilla DRF | 论据 sound | ✅ |
| v3 collect 1181/823 | 18.92s | 19.81s，数字一致 | ✅ 独立复现 |
| platform 分支 | py36-boot-fixes | cb1ef5b | ✅ |
| boot | check 0 issues | 实测 | ✅ |

**agent 这轮全诚实** —— 本会话首个无 over-reporting 轮。reporting 质量提升（或本轮 claim 全可复现）。

---

## 5. 阶段判定 —— 双里程碑达成

- **R12 boot 里程碑**: `call_command("check")` 0 issues
- **R14 collect 基线**: 1181 collected / 823 errors（独立复现）

从 review-1 "至今零次 Py3 运行时启动、仅 py_compile" 到现在 "boot 0 issues + 823 collect 基线"。**Gap C（OEP-7 rung 2）真正开始** —— 823→0 是下一阶段核心工作。

## 6. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第十四轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-14-20260723.md
—— 全清洁轮，双里程碑（boot + collect 基线）确认。

裁决速览（全实测复现）:
- ✅ constraint 7 pin（DRF 锁）+ platform py36-boot-fixes + boot 0 issues + collect 1181/823 独立复现。
- ✅ v2 keep DRF 3.11.2（Juniper vanilla DRF 论据 sound）。
- 823 collect error 含 vendored XBlock 测试成分（src/xblock-utils 等，连 6F），drive-to-zero 需分类。

下一阶段（Gap C: 823→0）:

w1. **分类 823 collection error**:
   跑 --continue 收集全 error 列表，按来源分:
   - platform 代码 Py2-ism（urlparse/iteritems/except-E,e/import-absolute/raise-E,V 等）→ 平台 fix
   - vendored XBlock 测试（src/xblock-utils/ora2/etc.）→ fork patch 或 skip
   按模式 batch-fix（review-10 建议: python-modernize/sed 批量，比逐个快）。

w2. **tox py3 allow-fail baseline（Gap C / OEP-7 rung 2 正式起点）**:
   建 tox.ini py36 env（allow fail）+ 跑全量，记失败基线。collect 823→0 后，跑真测试，记 test failure 基线。
   823 collection error 是第一道（import 阶段），过了才是 test failure。

w3. **ORA2/6F stub 真解（prod-gate，尾部风险）**:
   openassessment 从 settings 移除 + 空 stub 是 deferred。ORA2 是 GRADABLE_BLOCKS 运行时 XBlock。6F ora2+proctoring ~70K SLOC 无上游 Py3 fork —— patch/wait/replace 决策。这是唯一仍可能显著推后时间线的尾部风险。

w4. py36-base.txt 全量生成 from base.txt（所有 blocker pin 修，含 DRF 3.11.2 + 7 constraint）。

硬约束（不变，review-verdict §5）:
1. 共享 DB 安全: 真连 DB 用独立 py3 schema。
2. Py3 env 独立不动 Py2 devstack。
3. code fix 在 py36-boot-fixes 分支，新 fix 继续 commit + push 该分支。
4. **验证真跑（--continue 全基线 + 分类），不只信数字** —— 本会话活测贯穿，多轮抓 over-reporting + silent 漂移（pymongo、DRF），本轮首次全清洁。
5. diff/版本自跑 git/pip 验证。
6. platform 其他分支不动（现 py36-boot-fixes）。

回报格式: 每步「做了什么 / 命令+真输出 / 判定 / 下一步」。先做 w1（--continue 收集全 error + 按来源/模式分类），分类完 batch-fix platform 部分，再 w2 tox。
```
