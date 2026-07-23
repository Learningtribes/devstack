# Py3 迁移 — 执行审查第三轮 (Execution Review 3)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 完成的 f-i（git 层探针 + 残留工作流清单 + ipaddr 联动 + probe 表述修正）
> 输入: `py36-git-layer-probe-20260723.md` + `py3-dep-residual-workstream.md` + 更新后的 `py36-probe-result-20260723.md`
> 结论一句话: **"3.6 能 boot"成立（load-bearing 包验过），但"3.6 整体可建"仍未坐实 —— auth 包未测是最后一道；估时偏乐观。**

---

## 1. Git 层探针覆盖度 — INCOMPLETE，"12+ 通过"高估

探针表"✅ 通过"列 15 行，但实际只有 **7 个真 import 验过**:

**真验过 OK（7）**: django-celery / djangorestframework / django-pipeline / django-wiki / MongoDBProxy / pygeoip / codejail

**未完成/未测（8）**:
- ParsePy（timed out，"估 OK"）、crowdsourcehinter、edx-jsme、recommender-xblock —— 未完成
- **django-cas、django-oauth-plus、django-openid-auth、djangorestframework-oauth —— 未测**

后四个是 **auth 包**，老 Py2-era fork 最易有 Py3 问题。任一不兼容 → third_party_auth / OAuth 路径崩。"未测"是真实缺口。

**load-bearing 部分稳**: Django / DRF / django-celery（platform boot 经过）已验过 → "**3.6 能 boot**"成立；"**git 层干净**"不成立。探针 line 55"主体通过"措辞高估。

### 阻塞项裁决
- 2 XBlock 阻塞（acid-xblock / DoneXBlock `importlib.resources` 3.6 问题，声称"0 平台代码导入 纯测试"）—— **应验是否在 INSTALLED_APPS / 运行时加载**，别只信"纯测试"。若运行时加载，跳过不可行。
- 3 egg metadata 不匹配（edx-ora2 / xblock-done / edx-sga）—— 打包问题，sed fix，非 Py3 特有。✅

---

## 2. 残留工作流估时（+1.5-4d）— 偏乐观，best-case

| item | 文档估时 | 裁决 |
|---|---|---|
| git 层 25+（item 3）| 1d | ⚠️ 偏轻: 8 未测含 4 auth，"估兼容纯 Python"是假设非验证。1d 够 iff 全兼容；auth 有不兼容就撑破 |
| coursegraph 选项 A（py2neo 4+）| 0.5-1d | ⚠️ 偏轻: py2neo 3→4 API 变更大（`NodeSelector`/`authenticate` 4.x 移除，`Graph` API 改），3 文件但 5 API 全变，现实 1-2d。选项 C（移除评估）2-3d 合理 |
| SAML 若需适配 | 0.5d | ⚠️ 偏轻: prod 用 SAML 时 pysaml2 升 + xmlsec 替换 + 测 SAML 登录流是 1-2d，非 0.5d |
| ipaddr / beautifulsoup | 0d | ✅ 准确（ipaddr 随 #2322 消解；bs 仅 pynliner transitive，0 代码改动）|

→ +1.5-4d 是 **best-case**。若 auth 包有问题 + SAML 在用，现实 **3-6d**。范围应收宽或标注"假设全成立时"。

---

## 3. coursegraph + SAML 决策优先级 — 不一致

SAML 工作流正确地**先"确认 prod 是否启用 SAML"再 sizing**。**coursegraph 没有这一步** —— 直接跳到 A/B/C 选项 sizing。

应补 coursegraph 的"是否在 prod 使用"调查 gate（与 DCC 移除模式一致：不用 → C 移除最干净）。两个工作流应同样纪律: **先查 prod 用量，再选替换/移除**。

---

## 4. f-i 完成度裁决

| 任务 | 状态 | 裁决 |
|:---:|---|---|
| f | git 层探针 | ⚠️ 口径高估: 7 验过 + 8 未测（含 4 auth）。需补测 8 |
| g | 残留清单 | ✅ 结构对，但估时偏乐观，coursegraph 缺 prod-usage gate |
| h | ipaddr 联动 | ✅ 准确 |
| i | probe 表述修正 | ✅ 已改"PyPI 层干净，git 层待验" |

---

## 5. 给执行 agent 的补做动作

| 序 | 动作 | 理由 |
|---|---|---|
| j | **补测 8 个未测 git 包**: ParsePy / crowdsourcehinter / edx-jsme / recommender-xblock / **django-cas / django-oauth-plus / django-openid-auth / djangorestframework-oauth** —— 逐个 3.6 import 验，重点 4 auth | §1: "12+ 通过"高估，auth 未测是最后一道 |
| k | **验 2 XBlock 运行时加载**: 确认 acid-xblock / DoneXBlock 是否在 INSTALLED_APPS 或运行时加载，而非纯测试 | §1: 若运行时加载，"跳过"不可行 |
| l | **coursegraph 补 prod-usage gate**: 查 coursegraph 是否在 prod 用（Neo4j 课程图导出），不用 → C 移除评估优先于 A/B 替换 | §3: 与 SAML 同纪律，先查用量再 sizing |
| m | **估时范围收宽**: 残留清单 +1.5-4d → 标注"best-case；auth 有问题 + SAML 在用则 3-6d" | §2: 防乐观估时误导时间线 |

做完 j → Batch 1 落地 → 任务 D（tox py3 allow-fail baseline，攻 Gap C）。

---

## 6. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第三轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-3-20260723.md
—— 先整篇读完。

裁决速览:
- "3.6 能 boot" ✅ 成立（load-bearing 包 Django/DRF/django-celery 验过）。
- "3.6 整体可建" ❌ 仍未坐实 —— git 层探针"12+ 通过"高估，实际 7 验过 + 8 未测（含 4 auth 包）。
- 残留清单估时 +1.5-4d 偏乐观（best-case），现实 3-6d。
- coursegraph 缺 prod-usage gate（SAML 有，coursegraph 没有，不一致）。

你这轮要做 4 件 (j-m，详见 execution-review-3 §5):

j. 补测 8 个未测 git 包: ParsePy / crowdsourcehinter / edx-jsme / recommender-xblock / django-cas / django-oauth-plus / django-openid-auth / djangorestframework-oauth。逐个 3.6 容器 import 验。重点 4 个 auth 包（django-cas / django-oauth-plus / django-openid-auth / djangorestframework-oauth）—— 任一不兼容 third_party_auth/OAuth 路径崩。结果补进 py36-git-layer-probe-20260723.md，把"✅ 通过"列按实际状态拆分（真验 vs 未测），修正"12+ 通过"措辞。

k. 验 2 XBlock 运行时加载: 确认 acid-xblock / DoneXBlock(lbmdone-xblock) 是否在 INSTALLED_APPS 或运行时加载（grep lms/envs + cms/envs 的 INSTALLED_APPS / xblock entry points），而非纯测试包。若运行时加载 → "跳过"不可行，需升级到 Py3.7+ 兼容版或 patch importlib.resources backport。

l. coursegraph 补 prod-usage gate: 查 coursegraph（openedx/core/djangoapps/coursegraph）是否在 prod 用——查 lms/envs/aws.py / production settings 是否启用 Coursegraph 任务 + Neo4j 连接配置。不用 → 选项 C（DCC 移除评估）优先于 A/B 替换。把这一步加进 py3-dep-residual-workstream.md §1 顶部，与 §2 SAML 同结构。

m. 估时范围收宽: py3-dep-residual-workstream.md §汇总 +1.5-4d → 标注"best-case；若 4 auth 包有不兼容 + prod 用 SAML，则 3-6d"。

做完 j → Batch 1 落地（~2d: mysqlclient + pymongo 3.9 + memcached + egg 修复 + mongoengine smoke 已验）→ 任务 D（tox py3 allow-fail baseline，攻 Gap C）。
#2348 推 review 可与 j 并行（仍 REVIEW_REQUIRED）。

硬约束（不变，见 review-verdict §5）: 共享 DB 安全（Py3 首次 migrate 前独立 DB 名或 lock）/ mongoengine 0.10.0 + pymongo 3.9 为准 / 迁移修专用分支、migrations 不内联 removal 分支 / diff 数字自跑 git 验证别照搬。

回报格式: 每步「做了什么 / 实测命令+输出 / 判定 / 下一步」。先做 j（补测 8 git 包含 4 auth）——它是"3.6 整体可建"的最后一道。
```
