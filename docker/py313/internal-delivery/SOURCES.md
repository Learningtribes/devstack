# Registered source acquisition and SAML decision

All 20 local distributions below are delivered as source in the paired devstack
Git commit. Acquisition is `git checkout <manifest devstack runtime SHA>`; the
exporter verifies every file against `probe/startup-20261024-run01/frozen-local-inputs.json`.
The installer stages those files and registered archive expansions together in a
new venv. Neither old `/runtime` paths nor personal working copies are acquisition
inputs. Public packages come from the complete committed `internal-delivery.lock.txt`.
The source registry is the operational identity; platform `local-sources.json`
is historical observed metadata only. There are also ten editable distributions
from the paired platform commit, including the platform root.

An upstream version/directory label alone does not assert byte equality to PyPI
or a full VCS SHA. For preserved legacy snapshots without a complete upstream
archive record, the immutable acquisition identity is the paired Git tree plus
registry per-file SHA256. Do not reconstruct these from mutable upstream branches.
Existing `*-source.json` and `*PROVENANCE.md` records retain verified upstream
archive digests and LT commits where available. Access to the private paired
repositories is required; no credentials belong in the manifest.

| Source | Path relative to startup | Compatibility/identity note |
| --- | --- | --- |
| `MongoDBProxy` | `patched/MongoDBProxy` | Modern PyMongo proxy; client ownership and mutable mappings. |
| `django-ratelimit-backend-2.0` | `dependencies/django-ratelimit-backend-2.0` | Registered compatibility snapshot; inspect committed source and history for exact patch set. |
| `django-require-1.0.11` | `dependencies/django-require-1.0.11` | Registered compatibility snapshot; inspect committed source and history for exact patch set. |
| `django-splash-1.3.0` | `dependencies/django-splash-1.3.0` | Registered compatibility snapshot; inspect committed source and history for exact patch set. |
| `djangosaml2idp-lt` | `dependencies/djangosaml2idp-lt` | LT 0.3.3 processor, profile mapping and configuration retained; see SAML decision. |
| `dogapi-1.11.1` | `patched/dogapi-1.11.1` | Registered compatibility snapshot; inspect committed source and history for exact patch set. |
| `edx-search-5.0.0-lt` | `dependencies/edx-search-5.0.0-lt` | Official 5.0 base plus LT API/filter/HTTP views at 86ca377c34492ffac4633f342bd0c95c099b8398; modern ES adapter. |
| `edx-sga-0.28.0` | `dependencies/edx-sga-0.28.0` | Registered compatibility snapshot; inspect committed source and history for exact patch set. |
| `edx_completion-5.0.0` | `dependencies/edx_completion-5.0.0` | 5.0.0 learning-context API; immutable archive source JSON alongside directory. |
| `edx_drf_extensions-10.6.0` | `dependencies/edx_drf_extensions-10.6.0` | 10.6.0 plus fail-closed empty JWT verification keys and package collision fix. |
| `externality-xblock` | `patched/externality-xblock` | Registered compatibility snapshot; inspect committed source and history for exact patch set. |
| `fs-2.4.16` | `dependencies/fs-2.4.16` | 2.4.16 source with modern runtime compatibility. |
| `iframe-id-xblock` | `patched/iframe-id-xblock` | Registered compatibility snapshot; inspect committed source and history for exact patch set. |
| `ilt-xblock` | `patched/ilt-xblock` | Registered compatibility snapshot; inspect committed source and history for exact patch set. |
| `jazkarta-edx-jsme-690dbf7` | `dependencies/jazkarta-edx-jsme-690dbf7` | Retained legacy distribution snapshot; application retired by platform 919e976409d. No claim of upstream full SHA from abbreviated directory name. |
| `lbmdone-xblock` | `patched/lbmdone-xblock` | Registered compatibility snapshot; inspect committed source and history for exact patch set. |
| `pysaml2-7.5.5` | `dependencies/pysaml2-7.5.5` | 7.5.5 registered source; offline contract only, no real IdP. |
| `scormxblock-xblock` | `patched/scormxblock-xblock` | Registered compatibility snapshot; inspect committed source and history for exact patch set. |
| `xblock-pdf` | `patched/xblock-pdf` | LT PDF plugin; vendor PDF.js expanded from registered SHA256 archive. |
| `xblock_poll-1.15.1` | `dependencies/xblock_poll-1.15.1` | Registered compatibility snapshot; inspect committed source and history for exact patch set. |

## SAML version choice

Keep LT djangosaml2idp 0.3.3. Its installed processor contracts are
`has_access(user)`, `create_identity(user, mapping)` and configured/default
processor loading under `SAML_IDP_SPCONFIG`; LT profile/Country mappings and
integer IDs are preserved. The offline installed contract passes.

Compared immutable PyPI 0.7.2 source archive SHA256
`db634e18e3f3a07444215498bab43d0ab0ef09199d149d0cf1ee4cc44d8c7b48`:
it adds ServiceProvider and PersistentId database models, an entity_id processor
constructor, request-based `has_access`, and a different mapping orientation.
Replacing LT 0.3.3 would therefore change product/data contracts. There is no
real IdP or SSO interoperability claim. This decision is for the isolated new
development environment; production identity migration remains separate.

PDF.js is acquired from the committed registered archive
`registered-archives/pdfjs-public-build.tar.gz`, SHA256
`4feae9b8895e70caf65cb8c500bfb1f7c82641767eb1a3b7b7f3f887fc362c60`.
Its preserved vendor bytes are identified exactly; no upstream rebuild is claimed.
