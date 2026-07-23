# Py3 迁移 — 执行审查第二轮 (Execution Review 2)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 完成的 5 项确认动作 (task-a-e-completion-20260723.md) + 更新后的 py36-probe-result
> 输入: task-a-e-completion + py36-probe-result + 代码级 grep 验证（py2neo/dm.xmlsec/ipaddr 实际用量、base.txt git 包清单、verdict DONE 标记、#2348 review 状态）
> 结论一句话: **3.6 判定仍成立（PyPI 层坐实），但 git 层未测是真实残留；py2neo/coursegraph + dm.xmlsec/SAML 是两个未估时真实 Py3 工作流，需开清单。**

---

## 0. 重大发现：全量 resolve 排除了整个 git 层

探针方法（py36-probe-result §方法 line 8）："从 base.txt 提取**纯 PyPI 包**（排除 git+https / -e / file://）"。base.txt 有 **25+ 个 git 包**，全部被排除在 197 包 resolve 之外：

```
edx-ora2, django-celery, djangorestframework 3.6.3 fork, django-pipeline,
pystache_custom-dev, DoneXBlock, edx-sga, parse_rest, pygeoip, MongoDBProxy,
acid-xblock, codejail, crowdsourcehinter, django-cas, django-oauth-plus,
django-openid-auth, django-wiki, djangorestframework-oauth, edx-jsme,
xblock-lti-consumer, ...
```

→ "3.6 干净可建"是**窄属实**：仅 PyPI 层干净。git/vendored 层（Py2-era 老 fork 聚集地，含 verdict 标记的 6F 尾部 ~70K SLOC）在 3.6 上**未安装/未 resolve**。这恰是 Py3 代码兼容问题藏身处。execution-review 第一轮的"缺最后一发"（action a）只补了 PyPI 闭包，**git 层仍是空白**。

**表述修正**: 不得宣称"3.6 干净可建"，应为"PyPI 层干净，git 层待验"。

---

## 1. 四项审查重点裁决

### ① 3.6 全量 resolve 证据 — PyPI 层充分，git 层未测
- PyPI 197 包 resolve ✅，核心 import ✅ —— 这一发补上了，PyPI 层判定成立。
- 7 阻塞判"非 3.6 特有"**正确**（都 Py3 通用，不区分 3.6/3.8）。但其中**两个是真实 Py3 工作量**，不在任何 Batch 估时里（见 §2）。

### ② scoped Batch 1（~2d）— driver 层完整，但不是 Py3 dep 全貌
Batch 1 = mysqlclient + pymongo 3.9 + memcached + egg 修复 + mongoengine smoke（task b 已补）。作为**驱动层换装**完整。但**不含** py2neo/coursegraph、dm.xmlsec/SAML、git 层 25+ 包的 Py3 兼容 —— 独立工作流，需单独 sizing。

### ③ mongoengine 0.10.0 — task b smoke 通过，无遗漏
3.6 + pymongo 3.9 CRUD save/count/delete 全过，与 Juniper 验证一致。execution-review 第一轮提的 5 文件 smoke 关切**已闭合**。0.10.0 保持不动判定稳。

### ④ DCC 合并链路 — 合理，#2348 仍卡
实测 `gh pr view 2348`：仍 `REVIEW_REQUIRED`（task d 状态准确）。链路: merge #2322/2323/2324（APPROVED）→ #2348 补 review → Phase 4/5 rebase → M4.4-B 单独切。合理。顺带: **#2322 embargo merge 还消解 ipaddr 阻塞**（见 §2），额外收益。

---

## 2. 7 阻塞里的真实工作量（probe 低估）

代码级 grep platform/ 实际用量:

| 阻塞 | 实际用量 | 裁决 |
|---|---|---|
| **py2neo** (Py2-only) | `openedx/core/djangoapps/coursegraph/tasks.py` + compat + test utils（3 文件），真用 `Graph/Node/Relationship/authenticate/NodeSelector` | **真实工作**：换 py2neo 4+ / neo4j driver，或 coursegraph 走 DCC 移除评估。**不在 ~2d Batch 1**。probe"评估替换/删除"方向对但未 sizing |
| **dm.xmlsec.binding** (Py2-only) | 经 pysaml2 被 `lms/envs/aws.py` `saml2.sigver.get_xmlsec_binary` 用，third_party_auth SAML 签名路径 | **真实工作**：prod 若用 SAML 则不能"跳过"，需 SAML xmlsec 适配。**不在 ~2d Batch 1** |
| **ipaddr** | 仅 `embargo/models.py` + `embargo/forms.py`（2 文件） | **自动消失**: embargo 正被 DCC #2322 移除（APPROVED）。#2322 一 merge，ipaddr 用量归零。probe 没点出这个联动 |
| mysql-python / beautifulsoup / egg 不匹配 | shared，在 Batch 1 / 已知 | ✅ |

---

## 3. a-e 完成度裁决

| 任务 | 状态 | 裁决 |
|:---:|---|---|
| a | 全量 resolve | ✅ **口径窄了**: 只 PyPI 层，git 层排除。需补 git 层 resolve 探针 |
| b | mongoengine smoke | ✅ 闭合，无遗漏 |
| c | verdict 标 DONE | ✅ 已落实（line 42 `✅ DONE ... target=3.6`）|
| d | #2348 状态 | ✅ 准确（REVIEW_REQUIRED，需人工）|
| e | Django boot | ⏭️ 跳过合理（1.11 官方支持 3.6，灰桥已白）|

---

## 4. 给执行 agent 的补做动作

| 序 | 动作 | 理由 |
|---|---|---|
| f | **git 层 resolve 探针**: 在 3.6 容器装 25+ git 包（修 egg metadata 后），逐个 import 验，记录哪些 fork 在 3.6 崩/需补丁 | §0 重大发现: git 屄是空白，藏 Py3 兼容问题 |
| g | **开"Py3 dep 残留工作流"清单**: (1) coursegraph/py2neo（评估移除 vs 换 neo4j driver）(2) SAML/dm.xmlsec（评估 prod 是否用 SAML + 适配）(3) git 层 25+ 包逐个 | §2: 两个真实工作量未估时，需单独 sizing |
| h | ipaddr 标注"随 #2322 embargo merge 自动消解"，不单列工作 | §2: 联动，别重复劳动 |
| i | 更新 py36-probe-result 表述: "3.6 干净可建"→"PyPI 层干净，git 屄待验（见 §0）" | §0: 防过度宣称 |

做完 f → 才进 Batch 1 落地 → 任务 D（tox py3 allow-fail baseline）。

---

## 5. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第二轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-2-20260723.md
—— 先整篇读完。

裁决速览:
- 3.6 判定 ✅ 仍成立（PyPI 层坐实），但 git 屄未测是真实残留。
- a-e ✅ 完成（b/c/d 准确，e 跳过合理），唯一缺口: a 的"全量 resolve"口径窄了——排除了 25+ git 包。
- 两个未估时真实 Py3 工作流: py2neo/coursegraph + dm.xmlsec/SAML，不在 ~2d Batch 1 里。

你这轮要做 4 件 (f-i，详见 execution-review-2 §4):

f. git 屄 resolve 探针: 3.6 容器装 25+ git 包（先修 egg metadata: edx-ora2→ora2? 验证; xblock-done→lbmdone-xblock; edx-sga; pystache_custom-dev），逐个 import 验，记录哪些 fork 在 3.6 崩/需补丁。结果补进 py36-probe-result 新一节"§ git 屄 resolve"。
   git 包清单见 base.txt line 7-31（edx-ora2/django-celery/djangorestframework 3.6.3 fork/django-pipeline/pystache_custom-dev/DoneXBlock/edx-sga/parse_rest/pygeoip/MongoDBProxy/acid-xblock/codejail/crowdsourcehinter/django-cas/django-oauth-plus/django-openid-auth/django-wiki/djangorestframework-oauth/edx-jsme/xblock-lti-consumer）。

g. 开"Py3 dep 残留工作流"清单（新文件 devstack/docs/py3-dep-residual-workstream.md）:
   (1) coursegraph/py2neo — 评估: DCC 移除 vs 换 neo4j driver/py2neo 4+。用量: openeded/core/djangoapps/coursegraph/tasks.py + compat + test utils（3 文件）。
   (2) SAML/dm.xmlsec.binding — 评估: prod 是否用 SAML（third_party_auth）+ 适配 pysaml2 在 Py3 的 xmlsec 路径。入口: lms/envs/aws.py saml2.sigver.get_xmlsec_binary。
   (3) git 层 25+ 包逐个（来自 f 的结果）。

h. ipaddr 不单列: 在残留清单里标"随 #2322 embargo merge 自动消解"（embargo 是唯一消费者，2 文件）。

i. 更新 py36-probe-result 表述: "3.6 干净可建"→"PyPI 层干净（197 包），git 屄待验（见 § git 屄 resolve）"。

做完 f → Batch 1 落地（~2d: mysqlclient + pymongo 3.9 + memcached + egg 修复 + mongoengine smoke 已验）→ 任务 D（tox py3 allow-fail baseline，攻 Gap C）。
#2348 推 review 可与 f 并行。

硬约束（不变，见 review-verdict §5）: 共享 DB 安全（Py3 首次 migrate 前独立 DB 名或 lock）/ mongoengine 0.10.0 + pymongo 3.9 为准 / 迁移修专用分支、migrations 不内联 removal 分支 / diff 数字自跑 git 验证别照搬。

回报格式: 每步「做了什么 / 实测命令+输出 / 判定 / 下一步」。先做 f（git 屄探针）——它决定 3.6 是否真的整体可建。
```
