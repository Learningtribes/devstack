你是 Hawthorn Py3 迁移的审查 agent。入口文档：

1. `/Users/noahwang/workspace/hawthorn/devstack/docs/py36-git-layer-probe-20260723.md` — Git 层探针最终版
2. `/Users/noahwang/workspace/hawthorn/devstack/docs/py3-dep-residual-workstream.md` — 残留工作流（估时 +2-3d / +4-6d）
3. `/Users/noahwang/workspace/hawthorn/devstack/docs/py36-probe-result-20260723.md` — 3.6 探针概述

最新修正：
- **django-cas** ⏭️ skip（CAS feature-flagged off，Py2 devstack 也未安装）
- auth 最终：3/3 通过 ✅，0 阻塞
- "3.6 能 boot" ✅ 成立，1 个运行时阻塞：lbmdone-xblock（`importlib.resources`）
- 估时：best-case +2-3d，现实 +4-6d

可进 Batch 1 落地。
