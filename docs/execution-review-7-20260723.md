# Py3 迁移 — 执行审查第七轮 (Execution Review 7)

> Date: 2026-07-23 · Reviewer: Claude (审查 agent)
> 审查对象: 执行 agent 的 o1-o4 补做（`batch1-core-result-20260723.md` 第二版）
> 验证方法: 进 `py36-batch1` 容器真跑 pip show + import + MySQL 连接，非读文档
> 结论一句话: **o1/o2 ✅ 真达成；o3 pin 回 1.4.6 ✅ 但连接未独立复现（网络混淆）；o4 包装未 runtime 验；GRADABLE_BLOCKS 还有 runtime XBlock 未装。"完全验证"高估。**

---

## 1. 验证证据（py36-batch1 实测）

- **o1 git 包**: ✅ `pip show` 确认 django-celery 3.2.1+edx.2、MongoDBProxy 0.1.0 等装了。（我上轮 `import django_celery`/`mongo_proxy` 失败是**模块名错** —— django-celery 旧包 import 名是 `djcelery`；非未装。撤回上轮对 o1 的疑点。）
- **o2 shapely/ldap**: ✅ 两者 import OK，真运行时依赖已补。
- **o3 mysqlclient**: `pip show` → **1.4.6** ✅（pin 回到位，验证 review-6 的 flag）。但 DB-connect **我没复现**：container 是 bridge 网，连 `edx.devstack.mysql` → `Lost connection at handshake, system error: 11`；连 `127.0.0.1:3306` → `Can't connect (115)`。agent 用 `--network host` 测的（result doc 自述）。
- **o4 lbmdone**: `lbmdone-xblock 2.0.2` + `importlib_resources` 都装了（pip show）。XBlock 经 entry-point 运行时加载，非直接 import —— 我 `import lbmdone_xblock` 是错验证法。agent"需 Django runtime 验证"诚实。

## 2. o3 关键疑点 — "2.1.1 不兼容 MySQL 5.6" 结论可能被网络混淆

我测 **1.4.6** 也得 `system error: 11`（bridge 网，连 edx.devstack.mysql）。agent 报 **2.1.1** 也是 `system error: 11`（host 网）。同一错误码出现在两个版本上 → **`system error 11` 可能是网络层（bridge 连不上 devstack MySQL）非 mysqlclient 版本层**。

- pin 回 1.4.6 本身合理（Juniper 桥、贴近 Django 1.11 时代、dual Py2/3），无论连接问题如何。
- 但"1.4.6 连接成功 SELECT 1 OK"**未被独立确认**。需把 py36-batch1 接入 `devstack_default` 网或用 `--network host` 重测，确认 1.4.6 真连得上 MySQL 5.6。
- 若 host 网下 2.1.1 也连得上 → "2.1.1 不兼容"结论错，版本无关；若 2.1.1 仍崩 1.4.6 OK → 版本结论坐实。需对照测两个版本。

## 3. 新发现 — GRADABLE_BLOCKS 还有 runtime XBlock 未装

`cms/envs/common.py:333` `GRADABLE_BLOCKS = ['problem', 'scormxblock', 'ilt', 'lti', 'drag-and-drop-v2', 'lbmdonexblock', 'openassessment', 'library_content']`。实测:
- ✅ openassessment 装了
- ❌ **scormxblock / drag-and-drop-v2 / lti / library_content 未装**

这些是**运行时 XBlock**（SCORM 内容、拖拽、LTI consumer、库内容）。agent 归"各自工作流"延期，但它们在 GRADABLE_BLOCKS 里 → CMS 加载含这些 block 类型的课程时 XBlock 加载会崩。env 对含这些 block 的课程不 boot-ready。

## 4. 裁决

| 项 | 状态 | 裁决 |
|---|---|---|
| o1 git 包（11）| 装了 | ✅ 真达成（pip show 确认；撤回上轮模块名疑点）|
| o2 shapely/ldap | 装了 | ✅ 验证 |
| o3 mysqlclient 1.4.6 | pin 回 | ⚠️ pin ✅ 但连接未独立复现 + "2.1.1 不兼容"可能被网络混淆 |
| o4 lbmdone | 包装了 | ⚠️ runtime entry-point 未验（agent 自承）|
| GRADABLE_BLOCKS runtime XBlock | scormxblock/drag-drop/lti/library_content 未装 | ❌ "完全验证"高估 |

"可进 tox baseline"：对**平台单元测试**（多 mock XBlock）可能可行，但"依赖层完全验证通过"措辞过头 —— 含 scormxblock/drag-drop/lti 的课程不 boot-ready，lbmdone runtime 未验，MySQL 连接待 host 网确认。

---

## 5. 交接给执行 agent（复制下方）

```
你是 Hawthorn Py3 迁移的执行 agent。第七轮审查已落盘到
/Users/noahwang/workspace/hawthorn/devstack/docs/execution-review-7-20260723.md
—— 先读 §2（o3 网络疑点）+ §3（GRADABLE_BLOCKS 新发现）。

裁决速览（实测 py36-batch1，非读文档）:
- o1/o2 ✅ 真达成（pip show 确认；审查 agent 撤回上轮模块名疑点）。
- o3 mysqlclient 1.4.6 pin ✅，但 DB-connect 未独立复现 —— bridge 网连 edx.devstack.mysql 得 system error 11（与 agent 报 2.1.1 的错同码）。"2.1.1 不兼容 MySQL 5.6"结论可能被网络混淆，需 host 网对照测两版本。
- o4 lbmdone 包装了，runtime entry-point 未验（你自承）。
- 新发现: GRADABLE_BLOCKS 里 scormxblock/drag-and-drop-v2/lti/library_content 未装 —— runtime XBlock，含这些 block 的课程 CMS 不 boot-ready。"完全验证"高估。

你这轮补做:

p1. o3 网络对照测: 把 py36-batch1 接入 devstack_default 网（docker network connect devstack_default py36-batch1）或重建 --network host。然后对照测两个 mysqlclient 版本的真连接:
   - pip install mysqlclient==2.1.1 → SELECT 1（记结果）
   - pip install mysqlclient==1.4.6 → SELECT 1（记结果）
   两版在同网下对照，坐实"2.1.1 不兼容"还是"网络问题"。最终 pin 1.4.6（Juniper 桥）除非 2.1.1 同网也 OK 且有理由留新。落盘对照结果。

p2. o4 lbmdone runtime 验: 在 Django CMS 上下文验 XBlock entry-point 加载 —— XBlock.load_class('lbmdonexblock')（或 platform 的 block-loading 路径），确认 importlib_resources backport 让该 XBlock 类真能实例化，非仅 pip install。若崩 → patch fork 的 importlib.resources import（try importlib_resources backport）。

p3. 补装 GRADABLE_BLOCKS runtime XBlock（含这些 block 类型的课程 CMS boot 需要）:
   - scormxblock（SCORM 内容）—— platform src/ vendored 或 git pin
   - drag-and-drop-v2（xblock-drag-and-drop-v2，src/ vendored）
   - lti（xblock-lti-consumer git pin）
   - library_content（xmodule 内置，查为何未装 —— 可能 import 名非 xmodule_library_content，查实际模块）
   装后验 entry-point 加载（XBlock.load_class 各自 type name）。

p4. 全装齐后，跑一次真 Django boot smoke: DJANGO_SETTINGS_MODULE=lms.envs.devstack（或 py3 等效）+ django.setup() + call_command('check')，确认整个 LMS+CMS 能 boot（不只单包 import）。这是从"静态判断"转"运行时 boot 验证"的里程碑。

做完 p1-p4 → 才进 tox py3 allow-fail baseline（Gap C）。p4 boot smoke 通过是 tox 的真正前置。

硬约束（不变，review-verdict §5）:
1. 共享 DB 安全: p1/p4 连 MySQL 用独立 py3 schema，别碰 Py2 devstack 数据。
2. Py3 env 独立不动 Py2 devstack。
3. 迁移修专用分支，migrations 不内联 removal 分支。
4. Py3 兼容验证真跑（import / entry-point load / boot），不只 grep 或 pip show。pip show 装了 ≠ 运行时 OK（本会话多次教训：django-cas import 崩、lbmdone 需 runtime、XBlock 经 entry-point 非 import）。
5. diff/版本自跑 git/pip 验证，别照搬文档。
6. platform 其他分支不动。

回报格式: 每步「做了什么 / 实测命令+输出 / 判定 / 下一步」。先做 p1（mysqlclient 对照测）—— 它定 DB 层是否真通，是 p4 boot smoke 的前置。
```
