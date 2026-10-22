# Py3 迁移 — 执行审查第十八轮 (Execution Review 18) — 🏁 TOX BASELINE / Gap C 里程碑

> Date: 2026-07-24 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 的 tox baseline（progress-plan "Next Step: Tox Baseline"）
> 验证方法: docker exec 真跑 `pytest --ignore=src/pavelib/scripts --continue-on-collection-errors --tb=no -q`
> 结论一句话: **✅ TOX BASELINE VERIFIED —— 798 failed / 821 passed / 613 errors。Gap C（OEP-7 rung 2）里程碑达成，真 Py3 测试跑起来。821 passed = 迁移在测试层 demonstrably 工作。**

---

## 1. 验证证据（真跑，非 collect-only）

```
DJANGO_SETTINGS_MODULE=lms.envs.test python3 -m pytest \
  --ignore=src --ignore=pavelib --ignore=scripts \
  --continue-on-collection-errors --tb=no -q
→ 798 failed, 821 passed, 15 skipped, 628 warnings, 613 errors in 115.36s
```
- collect 1634/613 验证一致
- 1634 collected = 821 passed + 798 failed + 15 skipped
- 613 collection errors（deferred: nested 64 + 长尾）
- 错误样本: xblock_integration / completion_integration `AttributeError: 'str' object...`（Py3 str/bytes，review-1 csv/base64/hashlib 类）

## 2. 里程碑意义

**本会话最大信号**:
- R1 起点: "至今零次 Py3 运行时启动，仅 py_compile"
- R12: boot + check 0 issues
- R14: collect 基线
- **R18: 821 真 Py3 测试通过** —— 迁移在**测试层 demonstrably 工作**，不只是 boot

Gap C（OEP-7 rung 2 / review-1 标的"唯一真实方法缺口"）**真正达成** —— 测试环建立，可 drive-to-zero。

## 3. 工作队列

| 项 | 数 | 性质 |
|---|---|---|
| passed | 821 | ✅ 地基（Py3 测试工作）|
| failed | 798 | drive-to-zero 队列（OEP-7 step 4）|
| collection errors | 613 | deferred（nested 64 + 长尾 broken 文件）|

## 4. 下一关键分析 —— 798 failures 系统性 vs 分散

drive-to-zero 效率取决于:
- **系统性**（少数根因打中很多测试，如一个 helper bug 打 200 测试）→ 修几个点 failures 骤降，ROI 高
- **分散**（每个测试自己 Py3-ism）→ 长磨

策略分叉点。必须先聚类才能高效修。

---

## 5. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第十八轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-18-20260724.md
—— 🏁 TOX BASELINE / Gap C 里程碑 VERIFIED: 798 failed / 821 passed / 613 errors。

裁决速览（真跑验证）:
- ✅ tox baseline 真: 821 passed / 798 failed / 613 errors。Gap C（OEP-7 rung 2）达成。
- ✅ 821 passed = 迁移测试层 demonstrably 工作（R1→R18 从零运行时到 821 真测试过）。
- 798 failed = drive-to-zero 队列。613 collection errors deferred（nested + 长尾）。

下一阶段（drive 798→0，先聚类定策略）:

aa1. **聚类 798 failures 找系统性根因**（决定 drive-to-zero 效率）:
   docker exec py36-build bash -c 'cd /edx/app/edxapp/edx-platform && DJANGO_SETTINGS_MODULE=lms.envs.test python3 -m pytest --ignore=src --ignore=pavelib --ignore=scripts --continue-on-collection-errors --tb=line -q 2>&1 | grep -E "FAILED|Error|assert" | sed -E "s/.*: //; s/[0-9].*//" | sort | uniq -c | sort -rn | head -30'
   （--tb=line 每失败一行根因，按错误类型/消息聚类）
   输出 top 根因 + 命中数。判断: 系统性（top 几个根因占大 %）vs 分散。

aa2. **修系统性根因（高 ROI）**:
   - 若某 helper/util 的 Py3 str/bytes bug 打中 N 测试 → 修一处，N failures 消
   - 常见预期: csv/base64/hashlib str/bytes（review-1 标的 21 文件）、`iteritems` 残留、`unicode`、mock vs MagicMock Py3 差异、assert rewrite
   每修一个根因，重跑 baseline 记新 passed/failed。

aa3. **分散 failures 逐类扫**: 聚类后剩余的小类，按模式 batch（python-modernize 或 sed）。

aa4. **collection errors 613 并行降**: nested 64（A pin / C stub，不 B）+ 长尾 broken 文件 skip（norecursedirs）+ common Py2-ism batch（cPickle/urlparse/cStringIO）。collect 降 → 更多测试能跑 → failure 基线更全。

aa5. drive 798→低 + 613→低 后 → OEP-7 step 5（py3 tests gate build）→ step 7（stop testing py2）。

并行: ORA2/6F 真解（尾部风险，~70K SLOC）+ prod-gate 4 stub（SAML/coursegraph/enterprise/jwt，需 prod 配置）。

硬约束（不变，review-verdict §5）:
1. 共享 DB 安全: 测试用 lms.envs.test（SQLite），真连 DB 用独立 py3 schema。
2. Py3 env 独立不动 Py2 devstack。
3. code fix 在 py36-boot-fixes 分支，commit+push。
4. **验证真跑（pytest 真 run + --tb=line 聚类），不只信数字** —— 本会话活测贯穿，R18 tox baseline 真复现。
5. diff/版本自跑 git/pip 验证。
6. platform 其他分支不动（现 py36-boot-fixes）。

回报格式: 每步「做了什么 / 命令+真输出 / 判定 / 下一步」。先做 aa1（--tb=line 聚类 798 failures，贴 top 根因 + 命中数），聚类结果定 aa2 优先级。系统性根因先修（ROI 高）。
```
