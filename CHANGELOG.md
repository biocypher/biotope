# Changelog

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
