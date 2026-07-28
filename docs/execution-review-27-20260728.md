# Py3 迁移 — 执行审查第二十七轮 (Execution Review 27) — fcac4469 review + collection 12465 里程碑

> Date: 2026-07-28 · Reviewer: Claude (review agent)
> 审查对象: commit `fcac4469cf7`（41 文件，unblock legacy test + codec paths）
> 验证方法: git show diff + docker exec boot + collect + norecursedirs 检查
> 结论: ✅ **APPROVE**。bytes/text/crypto 修复正确，conftest 解锁 8x 测试发现（12465/81）。

---

## 1. 验证证据

- **HEAD** = `fcac4469cf7`（on top of `9e1bd6f86a3`）。41 文件，+188/−89。
- **boot** ✅ "System check 0 issues"
- **collection** ✅ **12465 collected / 81 errors**（16.44s）—— 从 R25 1480 → 12465（8x）
- **norecursedirs** 仍排除 src/（`src pavelib scripts` 在）—— collection 暴涨非 vendored 重新计入
- **目标证据**（execution agent 报）: verify_student encryption/signing 5 passed + base64 smoke + 全文件 compile + git diff --check ✅

## 2. Review focus 全过

### verify_student/models.py — base64/hex Py3 合约 ✅
- `.decode("hex")` → `binascii.unhexlify(six.ensure_binary(...))`
- `.encode('base64')` → `base64.b64encode(...).decode('ascii')`（CharField 需 str）

### util/models.py CompressedTextField ✅
- `.encode('utf').decode('base64')` → `base64.b64decode(value)`
- `.encode('base64').decode('utf8')` → `base64.b64encode(value).decode('utf8')`

### verify_student/image.py ✅
- `.decode("base64")` → `base64.b64decode(encoded_data)`

### verify_student/ssencrypt.py ✅
- rsa_encrypt/rsa_decrypt: `isinstance(text_type)` → `.encode('utf-8')`（data + key）
- `hmac.new(secret_key.encode('utf-8'), message.encode('utf-8'), sha256)`
- `b2a_base64(...).rstrip(b'\n').decode('utf-8')`（bytes→str header）

## 3. conftest 测试发现 8x（collection 里程碑）

conftest.py（root + common/test/conftest.py）改动解锁了 pytest 测试发现 → **12465 collected / 81 errors**（从 1480）。norecursedirs 仍排除 src/，所以是**真发现**（非 vendored 膨胀）。

这是 R18 tox baseline 以来的最大 collection 跃升 —— 几乎全测试套现在能 collect（81 errors 是残余）。

## 4. 裁决

| 项 | 状态 |
|---|---|
| boot | ✅ 0 issues |
| bytes/text/crypto | ✅ 正确（base64/hex/rsa/hmac 合约）|
| over-reach | ✅ 无（norecursedirs 在，无 settings/migrations/urls）|
| collection | ✅ 12465/81（8x 里程碑）|
| 目标证据 | ✅ verify_student 5 passed + smoke |

**APPROVE**。无 Critical/Major。

## 5. 当前 py36-boot-fixes

- HEAD `fcac4469cf7`，**25 commit** ahead of master
- boot ✅，collection **12465/81**
- full run 未完成（80% 后 21min 超时停 xmodule/contentstore）—— **新 baseline 待确立**（12465 surface 远大于之前 1480 时的 720-722/1445-1447）
- CSV 删除仍留未提交（无关）

## 6. 交接（给执行 agent）

1. **确立 12465 surface 下的新 full-run baseline** —— 需完整 pytest（可能需 `EDXAPP_TEST_MONGO_HOST=edx.devstack.mongo` + 长 timeout + Docker network connect devstack_default）。记 passed/failed/errors。**这是下一关键里程碑**（之前所有 baseline 都在 1480 surface，现 8x 大）。
2. **drive 新 baseline 的 failures**（`--tb=line` cluster at 12465 surface）—— landscape 完全不同。
3. **81 collection errors**（残余，cStringIO/io + tests.integration + provider 第三方）。
4. **ORA2/6F**（~70K SLOC，patch/wait/replace）—— 用户决策。
5. **prod-gate 4 stub**（SAML/coursegraph/enterprise/jwt）—— 用户查 prod。

## 7. 累积进度（R1 → R27）
- R1: 零运行时，仅 py_compile
- R12: boot 0 issues
- R18: tox baseline（821 passed at 1480 collected）
- R25: 1445 passed（broad sweep + modernize 单 fixer）
- **R27: 12465 collected / 81 errors**（conftest 解锁 8x 测试发现）+ bytes/crypto 修复 APPROVED

## 8. 教训新增（R27）
8. **conftest.py 是测试发现的杠杆点** —— 小改动可 8x collection（比逐文件修 collect error 高效得多）。类似 store_utilities SyntaxError 级联，但是发现层。
9. **Py3 crypto bytes 合约**: `.decode("hex")`→`binascii.unhexlify`、`.encode('base64')`→`base64.b64encode().decode('ascii')`、rsa/hmac 全需 `.encode('utf-8')` —— 标准模式，可参考 verify_student 实现。

## 9. 执行 agent 续作（2026-07-28，交接点）

- 新提交 `4661df6190f`（17 个 Python 文件，57 insertions / 33 deletions）已落盘；只包含平台源码，CSV 删除仍未 stage。
- course-run API 的 DRF `action`/JWT、PyMongo 3、transcript bytes/text、safe-session/API codec 修复已随提交固化。
- `cms/djangoapps/contentstore/views/course.py:909` 的默认 JPEG 已改为二进制模式 `rb`：`test_create` 两个参数化用例从 500 恢复为 **2/2 passed**。
- `common/lib/xmodule/xmodule/modulestore/split_mongo/split.py:249,260` 的 `dict.viewkeys()` 已改为 `six.viewkeys()`，消除了 rerun clone 的首个 Python 3 blocker。
- rerun 随后暴露安装包 `edxval==0.1.16` 的 `edxval.api.copy_course_videos()` 仍引用 Python 2 `unicode`；当前 course-run 文件结果为 **16 passed / 2 failed**，两例均卡在该外部包，不能算平台 rerun 已通过。
- 修改文件 `compileall` 通过；`git diff --check` 通过。LMS boot check 当前被同一依赖桥暴露的新问题阻断：安装的 `edx-when==1.3.2` 导入不存在的 `edx_rest_framework_extensions.auth` namespace（当前 extensions 为 1.5.2，只有 `authentication.py`）。此前 HEAD 的 0-issue boot 结论不可直接套用于该未解决依赖组合。

### Review agent next actions

1. 先复核 `4661df6190f` 的 17 文件 diff，重点检查 `rb`、`six.viewkeys`、JWT import 与 PyMongo fallback。
2. 在可控依赖环境中解决/验证 `edxval`（建议先评估 `edxval>=4.x` 与 Hawthorn API 的兼容性），再重跑两个 rerun 用例；不要在平台代码里静默吞掉 `copy_course_videos`。
3. 对齐 `edx-when` 与 `edx-drf-extensions` namespace 后重跑 LMS/CMS boot check；在此之前不要刷新 full-suite baseline。
4. 保持历史 baseline `720–722 / 1445–1447 / 586` 与 canonical collection `12464 / 81` 不变；本轮没有新的 full-suite 总数。
