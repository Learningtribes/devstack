# Py36 探针 — 全量 Resolve 确认

> Date: 2026-07-23 · ⚠️ 2026-07-23 修正：原写"3.6 干净可建"不准确。准确表述：**PyPI 层干净（197 包），git 层待验（~20 包，主体通过，见 py36-git-layer-probe-20260723.md）**。
> 容器: python:3.6 (CPython 3.6.15)

## 方法

1. 从 `requirements/edx/base.txt` 提取纯 PyPI 包（排除 git+https / -e / file://）
2. 修复 3 个预存阻塞：mysql-python→mysqlclient、beautifulsoup→bs4、ipaddr skip
3. `pip install` 剩余 ~198 个包
4. 验证核心包 import + 确认无误

## 结果

**197 个 PyPI 包全部 resolve 成功。** 核心包 import 验证：

```
Django 1.11.29     ✅
celery 3.1.25       ✅
kombu 3.0.37        ✅ (kombu.async 正常，async = soft keyword on 3.6)
pymongo 3.9.0       ✅
redis 2.10.6        ✅
elasticsearch 1.9.0 ✅
six 1.11.0          ✅
```

## 全量 base.txt 需修复的 7 个预存问题

所有问题 **均非 3.6 特有**，同样影响任何 Python 3 target：

| # | 包 | 问题 | 修复 | 3.6 特有？ |
|---|------|------|------|:---:|
| 1 | mysql-python==1.2.5 | Py2 only | → mysqlclient 1.4.6 | ❌ |
| 2 | ipaddr==2.1.11 | Py2 only | → stdlib ipaddress | ❌ |
| 3 | py2neo==3.1.2 | Py2 only | 评估替换/删除 | ❌ |
| 4 | dm.xmlsec.binding==1.3.3 | setup.py print 语句 | 需打补丁或跳过 | ❌ |
| 5 | pystache-custom-dev | git dep 链 | git 包存在但 -dev 标记问题 | ❌ |
| 6 | edx-ora2/xblock-done/edx-sga | #egg= metadata 不匹配 | sed 修正 | ❌ |
| 7 | beautifulsoup==3.2.1 | 2010 老包 | → bs4 | ❌ |

## 判定

**3.6 判定成立。** 全量 PyPI transitive closure 无 3.6 专有 wheel/sdist 缺口。base.txt 的 7 个阻塞通用于任何 Python 3 version，不削弱 3.6 选择。
