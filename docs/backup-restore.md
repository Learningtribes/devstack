# Hawthorn Devstack — Backup & Restore Guide

> M-series Mac (Apple Silicon) + OrbStack  
> Date: 2026-07-19

---

## 1. Data Tiering

| Tier | Data | Location | Size | Rebuildable? |
|------|------|----------|------|-------------|
| 🔴 Critical | MySQL (edxapp) | `devstack_mysql_data` | 21MB | ❌ All business data |
| 🟡 Important | MongoDB | `devstack_mongo_data` | ~100MB | ❌ Forum/course structures |
| 🟡 Important | Devpi pip cache | `devstack_devpi_data` | 659MB | ✅ But slow (network issues) |
| 🟢 Rebuildable | LMS/Studio static files | `devstack_edxapp_lms_assets` + `devstack_edxapp_studio_assets` | ~500MB | ✅ `paver update_assets` |
| 🟢 Rebuildable | Elasticsearch indices | `devstack_elasticsearch_data` | ~200MB | ✅ `reindex_course` |
| ⚪ Skip | node_modules | `devstack_edxapp_node_modules` | ~500MB | ✅ `npm install` |
| ⚪ Skip | Source code | bind mounts | — | ✅ `git clone/pull` |

---

## 2. Environment (Container) Backup

Rebuilding LMS/Studio from the base `ltdps/edxapp:latest` image takes 1-2 hours. Save the modified containers as new images.

**⚠️ LMS and Studio are independent containers** — each got its own in-container fixes (nodeenv, .deb, site-packages, venv/src). Commit them to **separate tags** so neither loses state:

```bash
docker commit edx.devstack.lms    ltdps/edxapp:m5-fixed
docker commit edx.devstack.studio ltdps/edxapp:m5-fixed-studio
```

Verification:
```bash
docker images ltdps/edxapp --format "{{.Repository}}:{{.Tag}}  {{.Size}}"
# ltdps/edxapp:latest          4.05GB
# ltdps/edxapp:m5-fixed        5.8GB   (lms)
# ltdps/edxapp:m5-fixed-studio 5.58GB  (studio)
```

**✅ Already wired (2026-07-20):** `docker-compose.yml` + `docker-compose-watchers.yml` now point `lms`→`m5-fixed` and `studio`→`m5-fixed-studio`. A `docker compose down -v` no longer loses the fixes — the next `up` recreates from these images. (Running containers keep `:latest` until recreated.)

**Note:** Re-commit (overwrite the tag) after any in-container modification (new pip packages, system packages, nodeenv changes), so the image stays current with the running container.

---

## 3. Data Backup Script

```bash
#!/bin/bash
BACKUP_DIR=~/workspace/hawthorn/backups/$(date +%Y%m%d_%H%M)
mkdir -p $BACKUP_DIR

# 1. MySQL (critical — 21MB, seconds)
docker exec edx.devstack.mysql mysqldump -uroot --databases edxapp edxapp_csmh \
  | gzip > $BACKUP_DIR/mysql_edxapp.sql.gz

# 2. MongoDB (important)
docker exec edx.devstack.mongo mongodump --archive \
  | gzip > $BACKUP_DIR/mongo.archive.gz

# 3. Devpi pip cache (optional — 659MB, saves download time)
docker run --rm -v devstack_devpi_data:/data -v $BACKUP_DIR:/backup \
  alpine tar czf /backup/devpi_data.tar.gz -C /data .

echo "Backup done: $BACKUP_DIR"
```

---

## 4. Data Restore Script

```bash
#!/bin/bash
BACKUP_DIR=$1  # Pass backup directory path

# 1. MySQL
gunzip -c $BACKUP_DIR/mysql_edxapp.sql.gz \
  | docker exec -i edx.devstack.mysql mysql -uroot

# 2. MongoDB
gunzip -c $BACKUP_DIR/mongo.archive.gz \
  | docker exec -i edx.devstack.mongo mongorestore --archive

# 3. Devpi (optional)
docker run --rm -v devstack_devpi_data:/data -v $BACKUP_DIR:/backup \
  alpine tar xzf /backup/devpi_data.tar.gz -C /data

# 4. Rebuild indexes and static files
docker exec edx.devstack.lms bash -c '
source /edx/app/edxapp/edxapp_env && cd /edx/app/edxapp/edx-platform && \
python manage.py lms reindex_course --all --settings=devstack_docker'

docker exec edx.devstack.lms bash -c '
source /edx/app/edxapp/edxapp_env && cd /edx/app/edxapp/edx-platform && \
paver update_assets lms --settings=devstack_docker'

docker exec edx.devstack.studio bash -c '
source /edx/app/edxapp/edxapp_env && cd /edx/app/edxapp/edx-platform && \
paver update_assets cms --settings=devstack_docker'

echo "Restore done from: $BACKUP_DIR"
```

---

## 5. Recommended Cadence

| What | When |
|------|------|
| MySQL dump | After every significant config change (Sites, Site Config, users) |
| Container commit | After any in-container modification (packages, nodeenv) |
| MongoDB + Devpi | Weekly, or before risky operations |
| Full backup | Before `docker compose down -v` or container rebuild |

---

## 6. Quick Reference

```bash
# Backup everything
docker commit edx.devstack.lms    ltdps/edxapp:m5-fixed
docker commit edx.devstack.studio ltdps/edxapp:m5-fixed-studio
mkdir -p ~/workspace/hawthorn/backups/$(date +%Y%m%d)
docker exec edx.devstack.mysql mysqldump -uroot --databases edxapp edxapp_csmh | gzip > ~/workspace/hawthorn/backups/$(date +%Y%m%d)/mysql.sql.gz

# Recreate from the fixed images (compose already points at them)
export DEVSTACK_WORKSPACE=/Users/noahwang/workspace/hawthorn
docker compose -f docker-compose.yml -f docker-compose-host.yml up -d lms studio

# Verify images exist
docker images ltdps/edxapp --format "{{.Repository}}:{{.Tag}}  {{.Size}}"
```
