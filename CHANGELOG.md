# Changelog

## [0.10.0](https://github.com/biocypher/biotope/compare/biotope-v0.9.1...biotope-v0.10.0) (2026-09-28)


### ⚠ BREAKING CHANGES

* **graph:** project validation callbacks and per-capability states are gone, so builds no longer verify scientific expectations; structural checks are not equivalent, and review-time independent reads replace them. interpretation no longer travels inside the graph; concept and property descriptions in schema_config.yaml, run.json policies and scope, and graph/ASSUMPTIONS.md replace the query context, so graph/build/ must travel with the graph. `biotope graph quality` prints its results instead of writing graph/reports/quality.json; `biotope graph metagraph` writes graph/metagraph.html by default. schemas are never re-rendered. Generated and 0.9 schemas no longer follow manifest changes; each change surfaces as source.drift for review. Authored types are not compared with Croissant dataType or nullability. new scaffolds bind fields through @ids scoped under their RecordSet; other ids produce source.unscoped_field, while an existing __field_refs__ mapping still binds them. a new package's name depends on the directories that already exist, so it can differ from a from-scratch generation. removed keywords such as SourceContract(generated=) and Pipeline(query_context=) fail with ordinary TypeErrors; run.json and definition reports are schema_version 2 (replacement and --report accept 1 and 2). See docs/migration.md for the 0.9 migration steps.
* **graph:** builds no longer write topology.json, ontology.ttl, query_context.json, provenance.jsonl or BiotopeQueryContext rows. Provenance is reached through each object's biotope_provenance_id in provenance.json. `biotope graph build` defaults to <graph>/build and replaces the previous generated build instead of requiring a new --out directory; --out still chooses another location. Export is headless and labels drop the namespace (for example Gene rather than CvdGene), so Entity is no longer reserved.

### Features

* **graph:** generate complete source inventories and check drift, retire validation and query context ([957b2ce](https://github.com/biocypher/biotope/commit/957b2ce2fda2174bf5c91b0a54b46e6dd3c1ae38))
* **graph:** integrate authored source contracts, staged builds and a provenance catalog ([4686916](https://github.com/biocypher/biotope/commit/468691669127d343f0fbb008afd76d388b966e90))


### Bug Fixes

* **add:** register byte-identical files once ([90a2838](https://github.com/biocypher/biotope/commit/90a283896c1f02a7ae59dae03c7fe53d3f313e1f))
* **add:** register byte-identical files that Baker parses once ([160e2ae](https://github.com/biocypher/biotope/commit/160e2ae9bf463ec690ec55537a4ce4eb2128f6f5))
* **add:** skip byte-identical copies before Baker parses them ([287bef0](https://github.com/biocypher/biotope/commit/287bef05d4ddc43d4bf2e3b7d791012b5ba16cf3))
* **graph:** check exported objects in a write that no build context checked ([924c06c](https://github.com/biocypher/biotope/commit/924c06c24657c3688b1be9ef03695b5b39fccf7d))
* **graph:** end a failed run with its error and log phases without a terminal ([845a229](https://github.com/biocypher/biotope/commit/845a229d4960a9b51c48b4ad3e1e8eb2606bb8df))
* **graph:** end a failed run with its finding code and log one line per phase ([907792e](https://github.com/biocypher/biotope/commit/907792e4428f80a894f8e14e9b32c20fe5649b7a))
* **graph:** keep descriptions of node properties named source or target ([bea90ae](https://github.com/biocypher/biotope/commit/bea90ae04e874b748c07268bd2e00a999ab8e37b))
* **graph:** record the libraries graph code imports and warn when they are undeclared ([789da09](https://github.com/biocypher/biotope/commit/789da09d77a9d0f4ea7d868426b2282c85f4449b))
* **graph:** refuse unexportable values when a mapping emits them ([7b4bdf1](https://github.com/biocypher/biotope/commit/7b4bdf19ab3f708e6dc48358b0fbf89043a452a5))
* **graph:** size the Neo4j read buffer to the export's longest line ([c2f6757](https://github.com/biocypher/biotope/commit/c2f6757e71616d63ddea615aec48ae5bd20f9bd9))
* **graph:** state the oversized-value threshold in characters and document the read buffer ([e2b5e82](https://github.com/biocypher/biotope/commit/e2b5e8210a7854931c82abddf9103346c2f74a1c))


### Performance Improvements

* **graph:** validate each value once per step and drop repeated work ([1fc51b7](https://github.com/biocypher/biotope/commit/1fc51b7a055acdc604d5bc16eb1b2f2bd609e910))


### Documentation

* document the 0.10 graph project shape and how to migrate to it ([31ee718](https://github.com/biocypher/biotope/commit/31ee7180422fca8e6d2becbfc84f4ab8e8376887))
* **skills:** describe structured files Baker cannot parse as record sets ([d70ae3d](https://github.com/biocypher/biotope/commit/d70ae3ddcc095f5113b7ffdb2dbb7d5a0935a33a))
* **skills:** install reader libraries from graph/pyproject.toml ([683efbb](https://github.com/biocypher/biotope/commit/683efbb1a2fc75d5ee812d898094521966f91aac))
* **skills:** rework biotope-croissant around the generated source inventory ([a1d8c92](https://github.com/biocypher/biotope/commit/a1d8c92d46f7fb56da1735b6da521c359a52a2a0))
* **skills:** say that aliases and missing-value tokens are declarations only ([5a7ffce](https://github.com/biocypher/biotope/commit/5a7ffcee319c71a04ddfd7513bee0ad36698fa58))


### Build System

* **release:** release breaking changes before 1.0 as a minor version and describe the package ([df3fa17](https://github.com/biocypher/biotope/commit/df3fa1733e86a8c4dd2ad903f198ed93e3cfdacd))


### Refactoring

* **graph:** raise value problems in one helper and share the item loop ([3c4e7dc](https://github.com/biocypher/biotope/commit/3c4e7dc375f2beff125df2e96b354f15703cd5f2))

## [0.9.1](https://github.com/biocypher/biotope/compare/biotope-v0.9.0...biotope-v0.9.1) (2026-09-15)


### Bug Fixes

* correct validation examples and documentation publishing ([b355807](https://github.com/biocypher/biotope/commit/b355807d75525e0a2c3ebfdb680c83e3a925d7bf))


### Documentation

* prepare Biotope documentation for the public release ([aa38846](https://github.com/biocypher/biotope/commit/aa3884629a0642d8709a8935ef564ea7eac301b1))
* prepare documentation for the public release ([17dd52d](https://github.com/biocypher/biotope/commit/17dd52db8b4c439f98a3802a4c4dbb186522e7ff))

## [0.9.0](https://github.com/biocypher/biotope/compare/biotope-v0.8.0...biotope-v0.9.0) (2026-09-15)


### Features

* add typed Python graph pipelines and update croissant-baker ([7c0b564](https://github.com/biocypher/biotope/commit/7c0b5646b4a94dc9a79b8ae083f27cf7b3493fbe))
* show bake progress, stream the baker's warnings, keep every checksum ([0360e5f](https://github.com/biocypher/biotope/commit/0360e5fa26af00843c2f0299ec321ffb782189d4))


### Bug Fixes

* **ci:** install published baker and honor Python matrix ([c758287](https://github.com/biocypher/biotope/commit/c75828733b7fc6e5a7e47d8f85218fa5f4fe292e))
* work with croissant-baker's compression-decoupling refactor ([73975fd](https://github.com/biocypher/biotope/commit/73975fd3b8e41ca4237463378a8fe443019b4ef2))


### Documentation

* finalize typed graph engine specification ([7a3614a](https://github.com/biocypher/biotope/commit/7a3614ac15b07fbaf5b82939dbd8723da84569c5))
* note the claims() refusal channel as deferred ([9465817](https://github.com/biocypher/biotope/commit/94658175a519362ef437c1db96783320e83cd0be))

## [0.8.0](https://github.com/biocypher/biotope/compare/biotope-v0.7.1...biotope-v0.8.0) (2026-06-29)


### Features

* decouple biotope runtime from biochatter and biocypher ([1a100f8](https://github.com/biocypher/biotope/commit/1a100f8e4c2a2a34d61349b0e3c0de2138b6dde3))
* decouple biotope runtime from biochatter and biocypherinitial commit ([11eb5f0](https://github.com/biocypher/biotope/commit/11eb5f06f54974b74638a99aa390a20d86ba72de))

## [0.7.1](https://github.com/biocypher/biotope/compare/biotope-v0.7.0...biotope-v0.7.1) (2026-05-28)


### Documentation

* **landing:** align commands surface and link tutorial as canonical onboarding ([#28](https://github.com/biocypher/biotope/issues/28)) ([2862055](https://github.com/biocypher/biotope/commit/2862055c7d5f6a3cdd635fcc76df88696d3c2de7))
* **tutorial:** admonition fixes + terminal-styled console blocks ([#30](https://github.com/biocypher/biotope/issues/30)) ([5e864b4](https://github.com/biocypher/biotope/commit/5e864b49555c8f74200ba371080971216fb0e24c))

## [0.7.0](https://github.com/biocypher/biotope/compare/biotope-v0.6.1...biotope-v0.7.0) (2026-05-25)


### Features

* **API:** Croissant-driven KG workflow + agent-supported knowledge ingestion ([#23](https://github.com/biocypher/biotope/issues/23)) ([57f1872](https://github.com/biocypher/biotope/commit/57f18728b71383712f9415c99f7d07cdeb81dd5e))

## [0.6.1](https://github.com/biocypher/biotope/compare/biotope-v0.6.0...biotope-v0.6.1) (2026-05-25)


### Documentation

* **examples:** add airports-notes.md and airport-hubs.csv ([#24](https://github.com/biocypher/biotope/issues/24)) ([29b1487](https://github.com/biocypher/biotope/commit/29b14878f177a408b03d2cffacc53b4a69f29ed6))

## [0.6.0](https://github.com/biocypher/biotope/compare/biotope-v0.5.0...biotope-v0.6.0) (2026-05-19)

### Features

- add bio.tools registry integration to search command ([72b996c](https://github.com/biocypher/biotope/commit/72b996cf190c02e3c35dba147cf10e5717bfc78c))
- add composite scoring option to search command ([d3c7d68](https://github.com/biocypher/biotope/commit/d3c7d681573cc32dd04041dd7d0ab7eb7bc074bf))
- Add GitHub star count ranking to biotope search ([7439f2b](https://github.com/biocypher/biotope/commit/7439f2bf064289ffea5a5f571f7abd0e925c9179))
- add MCP registry status to biotope status command ([668e720](https://github.com/biocypher/biotope/commit/668e720d33b7f2a5873efbc8811884f02453dd8c))
- enhance add and annotate commands to skip biotope's own annotation files ([f38063e](https://github.com/biocypher/biotope/commit/f38063ef473335a9032fcc9d5471e15289f88a09))
- enhance bio.tools integration with smart column labeling and composite scoring ([9d32b83](https://github.com/biocypher/biotope/commit/9d32b83a9aee094f0da89aed501885586c072de0))
- enhance file management capabilities with mv command and improved metadata handling ([#6](https://github.com/biocypher/biotope/issues/6)) ([21c9e3d](https://github.com/biocypher/biotope/commit/21c9e3d30aa83f0826045fa7e8357a2cda8c2c9a))
- **get:** Add file download and annotation command ([25de2a1](https://github.com/biocypher/biotope/commit/25de2a1850d973190482888e547005446212fa6f))
- git-like metadata management ([1cea6f6](https://github.com/biocypher/biotope/commit/1cea6f6ad8d289a68737138d958daab4e660d6e1))
- git-like metadata management ([1cea6f6](https://github.com/biocypher/biotope/commit/1cea6f6ad8d289a68737138d958daab4e660d6e1))
- implement biotope search command for MCP registry integration ([1aabef1](https://github.com/biocypher/biotope/commit/1aabef155cbab52df7c31f11f6b41fbe96dba740))
- implement registry infrastructure for BioContext integration ([dfebf6d](https://github.com/biocypher/biotope/commit/dfebf6d2e5286da15eee9594a20a4e505cb579ff))
- improve relevance scoring and GitHub API integration ([64ac804](https://github.com/biocypher/biotope/commit/64ac804308373ff6f7d11c23e48a943efbd23278))
- setuptools entry point ([7e1f4c5](https://github.com/biocypher/biotope/commit/7e1f4c56478d7fb884b68feeb21fcae97dc3b0cd))
- update init to more comprehensive workflow ([#4](https://github.com/biocypher/biotope/issues/4)) ([bab0fc7](https://github.com/biocypher/biotope/commit/bab0fc7f7e3d42a45d3702a98e196cdd0c8550ef))
- upgrade to git-on-top process, test battery, docs ([5531d10](https://github.com/biocypher/biotope/commit/5531d10f938a008c9f5de5f16c830f00ec3daf60))

### Bug Fixes

- improve error handling for registry cache loading ([efc1053](https://github.com/biocypher/biotope/commit/efc1053c4fc0e7c6c6994999783676a8adbd13c2))
- preserve registry ranking in combined search ([5106907](https://github.com/biocypher/biotope/commit/5106907d39490ebcf51263e099a2e8bfcf3111a7))

### Build System

- add release-please for automated version bumping ([6f82eba](https://github.com/biocypher/biotope/commit/6f82ebad2d8406866acc74764a1e8cdba0a473a2))

### Refactoring

- optimize score normalization in BioToolsRegistry ([c7d3791](https://github.com/biocypher/biotope/commit/c7d3791d5f3a305c7a445cfa7433ba7b7cb12518))
- streamline metadata context retrieval in Croissant file creation ([28001cb](https://github.com/biocypher/biotope/commit/28001cbbffffe01abb52af87e8a2b2634bc02b0f))
- streamline test setup and metadata handling ([4898529](https://github.com/biocypher/biotope/commit/4898529060560eab214161b1ce6dbded11dfa806))
- use sha256 to have the same hashes in different python sessions ([0ca1a16](https://github.com/biocypher/biotope/commit/0ca1a163862449b72178fab66a4acfdeaa6bc145))

## Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## \[Unreleased\]

- Upcoming features and fixes

## \[0.1.0\] - (1979-01-01)

- First release
