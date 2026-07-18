# XBlock Module Inventory & Path Standardization

> Date: 2026-07-19  
> Reference: preprod analysis from `platform-migration_discussion/docs/migration_discussion/04-infrastructure-dependencies.md` §6.1

---

## 1. Path Standardization

All XBlock source repos live under `src/` → bind-mounted as `/edx/src/` in containers.

| Directory | Container path | Status |
|-----------|---------------|--------|
| `src/xblock-scorm/` | `/edx/src/xblock-scorm/` | ✅ |
| `src/xblock-pdf/` | `/edx/src/xblock-pdf/` | ✅ |
| `src/xblock-ilt/` | `/edx/src/xblock-ilt/` | ✅ |
| `src/xblock-poll/` | `/edx/src/xblock-poll/` | ✅ |
| `src/xblock-drag-and-drop-v2/` | `/edx/src/xblock-drag-and-drop-v2/` | ✅ |
| `src/xblock-utils/` | `/edx/src/xblock-utils/` | ✅ |

Install command: `pip install -e /edx/src/<name>` (both LMS and Studio).

---

## 2. XBlock Inventory vs Preprod

### 2.1 Preprod src/ Packages (20 total) — All Verified

| # | Package | pip Name | LMS | Studio | Source |
|---|---------|----------|:---:|:------:|--------|
| 1 | acid-xblock | `acid-xblock` | ✅ | ✅ | venv/src |
| 2 | code-jail | `codejail` | ✅ | ✅ | venv/src |
| 3 | django-wiki | `django-wiki` | ✅ | ✅ | venv/src |
| 4 | done-xblock | `done-xblock` | ✅ | ✅ | venv/src |
| 5 | edx-jsme | `edx-jsme` | ✅ | ✅ | venv/src |
| 6 | edx-ora2 | `ora2` | ✅ | ✅ | venv/src |
| 7 | edx-proctoring | `edx-proctoring` | ✅ | ✅ | venv/src |
| 8 | edx-search | `edx-search` | ✅ | ✅ | bind mount |
| 9 | pygeoip | `pygeoip` | ✅ | ✅ | pip |
| 10 | rate-xblock | `rate-xblock` | ✅ | ✅ | venv/src |
| 11 | xblock-drag-and-drop-v2 | `xblock-drag-and-drop-v2` | ✅ | ✅ | src/ + venv/src |
| 12 | xblock-poll | `xblock-poll` | ✅ | ✅ | src/ + venv/src |
| 13 | externality-xblock | `externality-xblock` | ✅ | ✅ | venv/src |
| 14 | xblock-done | `lbmdone-xblock` | ✅ | ✅ | venv/src |
| 15 | iframe-id-xblock | `iframe-id-xblock` | ✅ | ✅ | venv/src |
| 16 | scormxblock-xblock | `scormxblock-xblock` | ✅ | ✅ | src/ |
| 17 | djangosaml2idp | `djangosaml2idp` | ✅ | ✅ | pip |
| 18 | code-block-timer | `code-block-timer` | ✅ | ✅ | venv/src |
| 19 | parse-rest | `parse-rest` | ✅ | ✅ | pip |
| 20 | pystache-custom | `pystache-custom` | ✅ | ✅ | venv/src |

### 2.2 Additional XBlocks Installed (beyond preprod doc)

| XBlock | pip Name | LMS | Studio |
|--------|----------|:---:|:------:|
| activetable-xblock | `activetable-xblock` | ✅ | ✅ |
| animation-xblock | `animation-xblock` | ✅ | ✅ |
| audio-xblock | `audio-xblock` | ✅ | ✅ |
| concept-xblock | `concept-xblock` | ✅ | ✅ |
| crowdsourcehinter-xblock | `crowdsourcehinter-xblock` | ✅ | ✅ |
| ilt-xblock | `ilt-xblock` | ✅ | ✅ |
| lti-consumer-xblock | `lti-consumer-xblock` | ✅ | ✅ |
| oppia-xblock | `oppia-xblock` | ✅ | ✅ |
| recommender-xblock | `recommender-xblock` | ✅ | ✅ |
| schoolyourself-xblock | `schoolyourself-xblock` | ✅ | ✅ |
| ubcpi-xblock | `ubcpi-xblock` | ✅ | ✅ |
| vectordraw-xblock | `vectordraw-xblock` | ✅ | ✅ |
| xblock-discussion | `xblock-discussion` | ✅ | ✅ |
| xblock-google-drive | `xblock-google-drive` | ✅ | ✅ |
| xblock-officemix | `xblock-officemix` | ✅ | ✅ |
| xblock-pdf | `xblock-pdf` | ✅ | ✅ |
| xblock-problem-builder | `xblock-problem-builder` | ✅ | ✅ |
| xblock-review | `xblock-review` | ✅ | ✅ |

**Total: 38 XBlocks installed, LMS and Studio identical.**

---

## 3. LMS vs Studio Sync Checklist

Before re-committing container images, verify LMS and Studio have identical packages:

```bash
diff <(docker exec edx.devstack.lms bash -c 'source /edx/app/edxapp/edxapp_env && pip list 2>/dev/null | grep -iE "xblock|ilt" | cut -d" " -f1 | sort') \
     <(docker exec edx.devstack.studio bash -c 'source /edx/app/edxapp/edxapp_env && pip list 2>/dev/null | grep -iE "xblock|ilt" | cut -d" " -f1 | sort')
```

No output = identical.

---

## 4. Container Backup

After any XBlock change:

```bash
docker commit edx.devstack.lms ltdps/edxapp:m5-fixed
docker commit edx.devstack.studio ltdps/edxapp:m5-fixed
```
