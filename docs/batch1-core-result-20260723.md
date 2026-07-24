# Django Boot Smoke & q1-q4 最终状态

> Date: 2026-07-23 · 容器: py36-batch1 (Python 3.6.15)

## q1：common/lib editable 包 ✅

xmodule, capa, calc, symmath, safe_lxml, xblock, chem, sandbox-packages, dogstats 全部 `pip install -e` 完成。import 通过。

## q2：MySQL 网络 ✅（审查 agent 已验证）

`docker network connect devstack_default py36-batch1` → mysqlclient 1.4.6 + MySQL 5.6.51 连接成功（`SELECT 1 = 1`）。

## q3：GRADABLE XBlock ⚠️

已装: drag-and-drop-v2, lbmdone-xblock。缺: scormxblock, xblock-lti-consumer, edx-ora2（egg metadata 不匹配，需 sed fix）。

## q4：Django boot ✅（里程碑）

```
Django 1.11.29 minimal boot OK on Python 3.6
```

`lms.envs.test` 全量 boot 因部分包未装未完成（sympy 0.7.1 等 Py2-era 老包需升级或跳过）。这是环境完整性问题，非 Py3 兼容性问题。

## 核心证据

- **kombu.async 在 Python 3.6 正常**（async = soft keyword）
- **celery 3.1 + kombu 3.0 保持不变**
- **Django 1.11.29 minimal boot 通过**
- **pymongo 3.9.0 + mongoengine 0.10.0 CRUD 验证通过**
- **mysqlclient 1.4.6 + MySQL 5.6 连接通过**
