# ltdps/edxapp:py36 — Python 3.6 固化镜像（docker commit）

> Date: 2026-07-23
> 基础: python:3.6 (CPython 3.6.15)
> 方法: docker commit from py36-batch1（网络受限，无法从 Dockerfile build）
> 大小: 660MB compressed
> 镜像: ltdps/edxapp:py36 (sha256:7760b943)

## 核心包

| 包 | 版本 | 说明 |
|------|------|------|
| Django | 1.11.29 | 官方支持 Py3.5–3.7 |
| celery | 3.1.25 | 保持不动（async = soft keyword on 3.6） |
| kombu | 3.0.37 | 保持不动 |
| pymongo | 3.9.0 | Juniper 验证版本 |
| mongoengine | 0.10.0 | 保持不动（Juniper 验证） |
| mysqlclient | 1.4.6 | Juniper 桥版本 |
| python-memcached | 1.59 | |
| elasticsearch | 1.9.0 | 保持不动 |
| redis | 2.10.6 | 保持不动 |

## 已安装的 editable 包（platform source）

- common/lib/xmodule, capa, calc, symmath, safe_lxml, chem, sandbox-packages, dogstats

## 已安装的 GRADABLE XBlocks

scormxblock, drag-and-drop-v2, lti-consumer, lbmdone-xblock, ora2

## Dockerfile（文档，非 build 来源）

文件: `devstack/docker/py36/Dockerfile`
由于 Docker 环境无法访问 Debian apt 源，实际镜像通过 `docker commit py36-batch1` 生成。
Dockerfile 保留作为环境文档和未来网络恢复后的重建参考。

## 使用

```bash
# 运行容器（需接 devstack_default 网络访问 MySQL/Mongo）
docker run -d --name lms-py3 \
  --network devstack_default \
  -v /Users/noahwang/workspace/hawthorn/platform:/edx/app/edxapp/edx-platform \
  ltdps/edxapp:py36 sleep infinity

# Django boot
docker exec lms-py3 bash -c '
  cd /edx/app/edxapp/edx-platform
  DJANGO_SETTINGS_MODULE=lms.envs.test python3 -c "
    import django; django.setup()
    print(\"Django boot OK\")
  "
'
```

## 注意事项

- 环境非 clean build（pip 批量安装后 Django 被升到 3.2 再 force-reinstall 回退）
- 网络恢复后建议用 Dockerfile 重建干净镜像
- py36-base.txt 位于 `devstack/docker/py36/py36-base.txt`（全部 working pins）
