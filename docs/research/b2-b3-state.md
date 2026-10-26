# Research: what B2 and B3 can reuse

> **Withdrawn specs.** The B2 (identity and precedence) and B3 (committed state) specs this note served were withdrawn on 26 October 2026, and PR #58, which implemented B2, was closed unmerged. They rebuilt inside biotope what 0.10 provides by design: identity resolution, source priority and human decisions are project code in `graph/alignment/` and mappings ([roadmap](../roadmap.md), decisions 9 to 11). Sections 1 and 2, on input checks and release history, still inform the new B2 spec, [releases and input checks](../specs/b2-releases-input-checks.md). Sections 3 to 5 describe pieces that now belong in a project, such as REACH's registry and corrections.

Researcher's note for the B2 (identity and precedence) and B3 (committed state) specs, 23 October 2026. Vlad asked to reuse existing tools and build only what is needed, and whether recording a hash of every input is too much. Checked against biotope `origin/main` (7d4f7d8), croissant-baker 0.6.0, mlcroissant 1.1.0 and REACH's `src/reach/ids.py`.

## 1. Input reproducibility: Croissant already hashes the files

What exists, verified in code and on a scratch project (`biotope init`, then `add` of a CSV, a folder of HTML pages, CSV shards and Parquet shards):

- Every FileObject croissant-baker writes carries `sha256`, `contentSize`, `contentUrl` and `encodingFormat`. Folders of pages and shards came out as one FileObject per file, each with its hash.
- A FileSet carries only `includes` globs and `encodingFormat`: the Croissant schema has no checksum on FileSet. Croissant-baker emits FileSets for FHIR NDJSON chunks and bundles, DICOM and NIfTI series, and Parquet partition tables. None of REACH's or InTRAC's inputs are of these kinds, and none of the scratch adds produced one.
- The dataset `version` defaults to `1.0.0` and is never bumped; `dateCreated` changes on every rebake. Neither identifies data.
- A contract revision in `.biotope/contracts/` digests a RecordSet's declaration only (`record_set_definition`), not the file's hash. It changes when the schema changes, not when rows change. Only a bare file's revision (`file_definition`) includes its `sha256`.
- `run.json` already records, per source, the manifest path, the manifest's digest, the contract digest and the whole `distribution` list, so every FileObject's `sha256`. It also records code digests and biotope's own source digest. B1's extracted records carry their document's digest.

So a release identifies its exact inputs by the manifests it read, which `run.json` already digests and copies. No new hashing format is needed.

The gaps:

- **Nothing checks the files at build time.** After editing `people.csv` without rebaking, `biotope check-data` reported it corrupted, `biotope status` showed nothing modified, and `graph build` reads the new rows while `run.json` records the old hash. The fix is to run the existing `check-data` comparison inside `graph check`/`build` and stop on a mismatch. That hashes the inputs at build time but records nothing new. A size and mtime cache can come later if hashing gets slow.
- **FileSets** have no member hashes. Until a project needs them, the build can refuse a FileSet source in a release, or record its members' hashes in `run.json`.
- **Committed state** (registry, decisions) is not in `run.json` yet. Digest each committed-state file the way `code_digests` digests code.
- **Retaining old inputs** is not covered: `data/` is gitignored, so a hash says which bytes a past release used but cannot bring them back. Decision 12 ("any past release can be rebuilt") needs the project to keep its inputs. REACH keeps each run under `data/raw/<run_id>/`. A project that wants more can put `data/` under DVC or git-annex; biotope need not.

Answer to Vlad: recording a hash of every input is not extra work, Croissant already does it for FileObjects. What is missing is checking the hashes during the build.

## 2. Release history and diffs: git plus a keyed diff

- **Plain git.** Committing each release's manifest (inputs, counts, problems, conflicts) and its diff summary gives history for free. Committing the records themselves suits small products like REACH's (5,631 nodes in the SQLite spike), not large ones.
- **DVC** (maintained by lakeFS since November 2025) tracks files by md5 in committed `.dvc` files and diffs them file by file. That duplicates Croissant's `sha256` and gives no record-level diff. Useful only for retaining inputs, as above.
- **git-annex**: the same file-level model, plus a Haskell binary. **lakeFS**: a server over object storage. Both are out of proportion here.
- **Dolt** gives row-level diffs by primary key, but it is a separate database binary that would hold the release. Too much for the lean rule.
- **Frictionless** data packages also hash resources, but have no history or diff; they overlap with Croissant.
- **daff** diffs two tables cell by cell, in a Python package translated from Haxe. It aligns rows heuristically unless given a key, and its output is for people, not for the release manifest.
- **BioCypher 0.17** writes import files and has no diff between builds.
- **SQLite export (PR #51)** gives each table `id TEXT PRIMARY KEY`, so `sqldiff` from the SQLite tools gives row-level SQL between two builds. It needs a binary that is not on PyPI, and its output is SQL statements, not a summary of added, removed and changed records.

Recommendation: biotope writes the diff itself. Releases are records keyed by ID, so the diff is a join on ID per entity, giving added, removed and changed records with their changed fields: a few dozen lines with no dependency. History is git over the release manifests.

## 3. ID registry: a committed JSON Lines file

No maintained small library does this. Bioregistry and idutils handle prefixes and identifier syntax, not minting. ARK and NOID minters target public persistent identifiers with resolvers, more than a local registry needs. REACH's `ids.py` (122 lines for two registries) shows the minimum:

- one entry per alias mapping it to an ID, and one per ID with the date it was first seen;
- new IDs issued as the highest number plus one; IDs are never deleted, which is what keeps them from being reused;
- a merge points the losing ID and its aliases at the surviving ID, and the losing ID stays as an alias, so anything that points at it still resolves;
- a sorted, atomic rewrite, so the git diff stays readable;
- for personal keys such as emails, a salted hash in place of the value. REACH needs this; biotope can offer it as an alias option.

Recommendation: a committed JSON Lines file plus about 60 lines in biotope.

## 4. Identity on declared keys: union-find, no linkage library

- **splink** is probabilistic linkage on DuckDB or Spark. Its deterministic mode links on SQL rules and clusters with connected components, but it does not flag contradicting keys, and it adds DuckDB.
- **recordlinkage** and **dedupe** are built around scored or learned matching. Their exact-key parts are blocking steps, not a clustering result.
- **networkx** is already installed through mlcroissant. `networkx.utils.UnionFind` or `connected_components` cluster records that share a key value.

The part no library does is the conflict rule: a cluster holding two different values of a key declared single-valued, such as two ORCIDs, is flagged and its records stay apart. That is a check over each cluster after union-find. Recommendation: networkx's `UnionFind`, or an equivalent 20-line union-find, plus that check in biotope. Fuzzy matching stays project code that returns proposed pairs.

## 5. Decisions and precedence: SSSOM for match decisions only

- **SSSOM** (1.0, August 2024; 1.1 in alpha) fits match and no-match decisions. A row is `subject_id`, `predicate_id` (`skos:exactMatch`), `object_id` and `mapping_justification` (`semapv:ManualMappingCuration` for a person, `semapv:MappingReview` for a reviewed proposal). `predicate_modifier: Not` records a rejection. `author_id`, `mapping_date`, `confidence` and `comment` cover who, when and why, and 1.1 adds `record_id`. IDs must be CURIEs with a prefix map, which a registry with a project prefix gives. sssom-py reads and validates it, but a project can write the TSV by hand, so biotope need not depend on it.
- SSSOM has no field overrides, link exclusions or added links. No standard covers these with less than a small biotope format. PROV-O offers the terms (`prov:wasAttributedTo`, `prov:generatedAtTime`, `prov:wasDerivedFrom`, `prov:wasInvalidatedBy`) but no file layout.
- **Frictionless** and Croissant describe data, not decisions about records.
- Field precedence is configuration: an ordered list of sources per field, which no standard covers. The conflict list belongs in the release manifest.

Recommendation: match decisions as an SSSOM TSV, read with the standard library; overrides, exclusions and added links as one small JSON Lines format whose field names reuse PROV-O and SSSOM terms (`author_id`, `mapping_date`, `comment`). Decision 11's rules apply to both.

## Sources

- biotope `origin/main`: `biotope/graph/sources.py`, `targets.py`, `check.py`, `build.py`, `commands/check_data.py`; PR #51.
- croissant-baker 0.6.0 `handlers/`; mlcroissant 1.1.0 `nodes/file_set.py`, `file_object.py`.
- SSSOM schema, `mapping-commons/sssom` `sssom_schema.yaml`, release v1.0.0 and v1.1.0a5.
- lakeFS, "lakeFS acquires DVC", November 2025.
