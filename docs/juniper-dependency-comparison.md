# 上游过渡策略：Ironwood → Juniper 的依赖变更全景

> Date: 2026-07-23
> Source: `upstream/open-release/ironwood.master` vs `upstream/open-release/juniper.master` 逐包对照

---

## 上游有 Py2→Py3 过渡版本吗？

**没有正式 release，但有过渡期。**

- **Ironwood**（2019-03）— 最后一个 **Python 2 only** release
- **Juniper**（2020-06）— 第一个 **Python 3 only** release
- **中间** — 3.5 个月的 master 分支 **dual-stack 过渡期**

---

## 上游过渡时间线（精确到 commit）

```
2018 (Ironwood 开发期)
  │
  ├── 4f12be08940  python-modernize 首次运行
  │                添加 from __future__ + six 模式到 Py2 代码库
  │
2019-09-12
  │
  ├── d1728b3d6a9  🔑 首次添加 Py3.5/3.6/3.7 到 tox，保留 Py2.7
  │                envlist = py{27,35,36,37}-django{111,20,21}
  │
  │   ╔══════════════════════════════════════════╗
  │   ║  3.5 个月 DUAL-STACK 过渡期             ║
  │   ║  Py2.7 + Py3.5+3.6+3.7 同时测试         ║
  │   ║  1436 commits（多数常规开发）             ║
  │   ║  Py3 专项修复:                          ║
  │   ║  - boto2 S3 bytes 处理                  ║
  │   ║  - bokchoy Py3 fixes                   ║
  │   ║  - 各种 Py3 兼容 patch                  ║
  │   ╚══════════════════════════════════════════╝
  │
2019-12-26
  │
  ├── b2046f6674e  🔑 从 tox 移除 py27
  │                envlist = py{35,36,37}-django{111,20,21}
  │                "Switch make upgrade to Python 3.5"
  │
2019-12-30（4天后）
  │
  ├── 9cf2f9f298e  运行 2to3 -f future . -w
  │                删除所有 from __future__ 导入
  │                2829 文件变更
  │
2020-06
  │
  └── Juniper 发布
```

**关键点**：`from __future__` 和 `six` 是在 **Py2 时代（2018）** 就已经加上的——通过 `python-modernize` 批量运行。dual-stack 期间这些代码已经在 Py2 生产上 bake 了至少一年。

---

## 上游过渡期做了什么（2019-09-12 → 2019-12-26）

| 阶段 | 做什么 | 多久 |
|------|------|:---:|
| **前期**（Ironwood 时代） | `python-modernize` 批量添加 `__future__` + `six`，Py2 生产 bake | ~1 年 |
| **过渡期** | tox 同时跑 Py2.7 + Py3.5/3.6/3.7，修 Py3 专属 bug | **3.5 月** |
| **切換** | 从 tox 移除 py27，转为 Py3-only | 1 天 |
| **清理** | `2to3` 移除 `from __future__` 导入 | 1 天 |
| **发布** | Juniper Py3-only release | 6 个月后 |

---

## 与我们的对比

| 维度 | 上游 | 我们 | 差异 |
|------|------|------|:---:|
| 现代化时机 | Ironwood 时代（Py2-only） | 现在（Py2-only） | ✅ 一致 |
| 现代化手段 | `python-modernize` | `python-modernize` + 手动 | ✅ 一致 |
| Py2 bake 时间 | ~1 年 | 当前进行中 | 我们更短 |
| Dual-stack 时长 | **3.5 个月** | 待定 | — |
| Dual-stack 测试 | tox py27+py35 同时跑 | 尚未建立 | 🔴 差距 |
| Celery 版本 | 3.1（没动）| 需升 4.4 | 我们更难（target 3.8） |
| Django 版本 | 1.11 → 2.2（同期升级）| 保持 1.11 | 我们更保守 |

**结论**：我们的策略与上游完全一致——先在 Py2 上现代化（`six` + `__future__`），再建立 dual-stack 测试，修 bugs，最后切換。上游的 dual-stack 只持续了 3.5 个月就干净切換了，这个速度值得参考。

**唯一没对齐的**：上游在过渡期有 tox py2+py3 同时跑。我们目前还没有 Py3 测试回路——这是 OEP-7 Gap C（唯一幸存差距）。

---

## Ironwood → Juniper：哪些变了，哪些没变

| 包 | Ironwood（Py2 末版）| Juniper（Py3 首版）| 变化 |
|------|------|------|:---:|
| Django | **1.11.29** | **2.2.16** | 🔴 跳大版本 |
| celery | 3.1.25 | 3.1.26.post2 | 🟢 +0.0.1 |
| kombu | **3.0.37** | **3.0.37** | 🟢 **零变化** |
| pymongo | 2.9.1 | **3.9.0** | 🟡 2.9→3.9 |
| mongoengine | **0.10.0** | **0.10.0** | 🟢 **零变化** |
| MySQL 驱动 | MySQL-python | **mysqlclient 1.4.6** | 🔴 替换包 |
| redis | **2.10.6** | **2.10.6** | 🟢 **零变化** |
| elasticsearch | **1.9.0** | **1.9.0** | 🟢 **零变化** |
| python-memcached | ~1.48 | **1.59** | 🟢 +0.11 |
| lxml | 3.8.0 | **4.5.0** | 🟢 3.8→4.5 |
| Pillow | ~3.4 | **7.1.2** | 🟢 3.4→7.1 |
| PyYAML | ~3.12 | **5.3.1** | 🟢 3.12→5.3 |
| six | 1.11.0 | **1.14.0** | 🟢 +0.3 |
| edx-celeryutils | ~0.2.7 | **0.5.0** | 🟢 +0.3（pin 不变：`celery<4.0`） |

**真正的变更只有 4 项**：Django 2.2、pymongo 3.9、mysqlclient 替换、常规包升级。

**6 个包零变化**：kombu、mongoengine、redis、elasticsearch 完全没动。

---

## 上游为什么能不动 celery/kombu

因为 Juniper 的 Python 目标是 **3.5**（后来加了 3.8 env，但那是后续的事）。

Python 3.5 中 `async` 是 "soft keyword" — 只在 `async def` 内部是关键字，`kombu.async` 作为模块名可以正常 `import`。Python 3.7 才把它变成完全保留字。

```
Ironwood (Py2)  ──→  Juniper (Py3.5)  ──→  (后来) Juniper Py3.8
celery 3.1.25   ──→  celery 3.1.26    ──→  需要 celery 4.x（但我们 fork 在这停了）
kombu 3.0.37    ──→  kombu 3.0.37     ──→  同上
```

**他们恰好停在 `async` 变成保留字之前的那个 Python 版本。**

---

## 这对我们意味着什么

### 可以直接照搬的部分（零风险）

```
redis 2.10.6         → 不动      ✅
elasticsearch 1.9.0   → 不动      ✅
python-memcached 1.59 → 跟 Juniper ✅
mysqlclient 1.4.6     → 跟 Juniper ✅
lxml ≥4.5.0           → 跟 Juniper ✅
Pillow ≥7.0           → 跟 Juniper ✅
PyYAML ≥5.3           → 跟 Juniper ✅
six 1.14+             → 跟 Juniper ✅
```

### 可以更保守的部分（Juniper 验证过的路径）

```
pymongo 3.9.0         → 用 3.9 而非 3.12 ✅ （Juniper 验证过的精确版本）
mongoengine 0.10.0    → 不动      ✅ （Juniper 验证了 0.10.0 + pymongo 3.9 兼容）
```

### 无法照搬的部分（我们需要自己解决）

```
celery 4.4.7          → Juniper 没走这条路（他们停在 3.1）
kombu 4.6.11          → 同上
edx-celeryutils fork  → 同上
Django 1.11 + Py3.8   → Juniper 跳到了 2.2，没走这条路
```

---

## 精简到极限的 Batch 1

最大程度参考 Juniper 后：

```
1. mysqlclient 1.4.6                     🟢 0.5d  照搬 Juniper
2. pymongo 3.9.0（Juniper 精确版本）       🟡 1d    照搬 Juniper，非 3.12
3. mongoengine 0.10.0  →  不动            ✅ 0d    Juniper 验证过了
4. python-memcached 1.59                  🟢 0.5d  照搬 Juniper
5. celery 4.4.7 + kombu 4.6.11            🔴 3-5d  无法照搬，必须做
6. edx-celeryutils fork                   🟡 1d    无法照搬，必须做
7. Django 1.11.29 + Py3.8 smoke spike     🟡 0.5d  无法照搬，必须做
8. lxml/Pillow/PyYAML/six 升级            🟢 0.5d  照搬 Juniper
                                   ─────────
                                   总计 ~7d
```

**从 ~10 天 → ~8 天 → ~7 天**：每次都因为参考 Juniper 而减压。

---

## 最终原则

**上游的「最小变更」哲学比我们的「桥版本」哲学更激进：能不动的全不动。**

| 我们的初始策略 | 上游实际 | 修正 |
|------|------|------|
| 每个包都找桥版本 | 大多数包根本不需要桥 | 只有 pymongo、mysql 驱动、celery 是真需要 |
| mongoengine 升到 0.19 | 0.10 不动 | 先不动，验证即可 |
| pymongo 升到最新 3.12 | 3.9 够了 | 可以保守用 3.9 |
| 所有都先升 | 能不升就不升 | **最小变更** |

**上游在 Ironwood→Juniper 之间只真正改了 4 样东西**，其余的要么完全不碰，要么是常规版本 bump。我们因为要 target 3.8 而非 3.5，所以 celery 这关逃不掉，但 mongoengine 和 pymongo 可以极端保守。
