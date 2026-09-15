# Development ideas

These are possible directions, not implemented features or release commitments.
Discuss proposed work in [GitHub issues](https://github.com/biocypher/biotope/issues)
before depending on it in a project.

## Persistent scan history

`biotope add --json` already provides per-file outcomes and diagnostics. A project
index could retain successive reports, compare coverage and help resume large scans.

## Larger graph builds

Graph objects and provenance currently accumulate in memory. Disk-backed state
could support larger builds while retaining conflict detection, deduplication and
endpoint validation.

## Stable requirement identifiers

Pipeline bindings currently reference the exact text of purpose requirements.
Stable identifiers could preserve those bindings when descriptions are edited.

## Richer source contracts

Generated source types cover scalar, nested and repeated records. Opaque arrays
need an explicit interpretation of grain and access. Further work could represent
those choices without treating every matrix element as a graph record.

## Database integration

Builds produce files for import. Optional integration could validate imports and
run declared query examples against a selected database version. This would need
separate credentials, lifecycle controls and database-specific tests.
