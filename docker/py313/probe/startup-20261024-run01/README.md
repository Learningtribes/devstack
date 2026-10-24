# Python 3.13 local runtime checkpoint

Captured 2026-10-24. This is a checkpoint of an existing development runtime,
not a successful empty-environment rebuild or a production migration recipe.
Do not run initialization or seed scripts against existing/production databases.

## Contents

- D01: Dockerfile, local settings, schema inspection/bootstrap/reconciliation,
  seed helpers and HTTP/worker entry points. Schema bootstrap uses model sync;
  migration-state correctness remains unverified. Site IDs and database names
  are specific to this existing local environment.
- D02: installer scripts, dependency inputs and adapted dependency sources.
  Existing source metadata and licenses are retained. Retired DOP inputs,
  upstream tarballs, caches and build metadata are excluded from Git.
- D03: runtime acceptance probes, small fixtures and asset replay scripts.
  These probes are preserved; this commit session did not rerun all probes.

## Required local state and restoration

Secrets remain in .env, .acceptance-credentials.json and jwt-private.pem;
none is committed or included in the checkpoint archives. Supply fresh local
credentials and a local signing key separately when rebuilding.

The protected archive at
/Users/noahwang/docs/hawthorn/py313-commit-artifacts-2026-10-24/run-01/devstack-working-files.tar.gz
preserves nonsecret startup inputs, generated assets, themes and theme-inputs.
Inspect archive member names before restoring into a NEW scratch directory;
never extract over the running checkout. Members are relative to the devstack
repository root. Compare hashes with devstack-file-hashes.json before reuse.
The theme builder currently requires theme-inputs/dce4781ddd25/hawthorn;
Git alone does not restore that copy. See checkpoint-manifest.json for the
source commits. created-resources.json is local resource metadata, not a DB backup.
Older Goal A/B and solver directories remain untouched and outside these commits
and the startup archive. No database or runtime-volume backup was performed.

## Known gaps

runtime-bootstrap.txt still contains file:///work/patched paths; install.sh
runs pip check and can stop on the seven known dependency conflicts. This is
not a portable lock file. Full authorization/organization/LT and SCORM matrices,
formal schema review, expanded restart persistence, an empty venv with second
isolated databases, and a complete browser rebuild loop remain pending.
HS256 issued-token evidence and the separate RS512 JWKS probe are distinct.
Discussion/wiki plugin loading still needs repair and explicit verification.

Prior runtime evidence lives under
/Users/noahwang/docs/hawthorn/py313-startup-artifacts-2026-10-24/run-02/.
Never reuse that evidence as proof that each intermediate commit runs alone.
