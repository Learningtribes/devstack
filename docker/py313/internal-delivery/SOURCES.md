# External source pins and SAML decision

The 20 distributions that were vendored in this repository (`patched/`, `dependencies/`,
`registered-archives/`, `frozen-local-inputs.json`) are no longer delivered from here.
Platform owns them as explicit inputs: git SHA pins on `py3-master` branches of the
Learningtribes repositories, versioned companion archives with readable patches, and the
Platform application lock. The per-distribution table, base commits, hashes and the
verification are in Platform
`docs/specs/migration/py313-external-dependency-pins-20261102.md`.
`probe/startup-20261024-run01/internal-delivery.lock.txt` remains the immutable paired
base lock recorded by the Platform manifest (`paired_lock_sha256`).

The vendored directories remain available in this repository's Git history before the
removal commit; there is no other acquisition path. Historical evidence documents in this
directory describe the former registered-source flow and are not edited.

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

The PDF.js build files are tracked in the Learningtribes `xblock-pdf` `py3-master` commit; the
former registered archive is no longer a Devstack input.
