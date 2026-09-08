---
name: biotope-croissant
description: Describe local datasets with croissant-baker, capture research purpose and target entities/relations, and author structurally checked mappings with the Biotope CLI. Use for Biotope, Croissant metadata, source-field mapping, or preparing mixed-format data for a knowledge graph. The supported workflow stops at mapping; it does not load values, transform data, build graphs, or query databases.
---

# Biotope: describe data and define mappings

Use the Biotope CLI, its help and errors. Do not import Biotope internals or edit
managed `.biotope/` files. Author mapping YAML under `mappings/`.

## Environment and project

Use the environment the user installed. For this unreleased integration, both
Biotope and the merged croissant-baker must be installed from their local
checkouts in that environment; `uvx` or an unqualified package install may use an
older release. Verify `biotope --version` and the Python package locations.

```bash
uv pip install --python .venv/bin/python -e /path/to/croissant-baker -e /path/to/biotope
.venv/bin/biotope --version
```

Choose the project root from the user's intent. `biotope init . --no-prompt`
initializes the current directory; `biotope init my-project --no-prompt` creates
a subdirectory, which you must enter before continuing. Keep Git enabled for a
new project: tracking commands locate `.biotope/` together with `.git/`.
Do not overwrite an existing project. Reuse its configured purpose and scope.

## Workflow

```text
local files → add → inspect → purpose and target schema → mapping → structural checks
```

### 1. Orient

Establish what the researcher wants to answer and which entities and relations
matter. Use answers already provided. Ask about missing choices or conflicts;
file shapes alone do not establish research intent. Read existing intent with
`biotope map --show`. Do not silently replace it or clear declared schema slots.

### 2. Describe selected local data

Data must be inside the project root. Honor the user's chosen input scope,
including a full-directory scan when requested. If scope is unspecified, start
with a small useful subset and report that selection. Do not scan environments, copied skills,
logs or previous outputs. Biotope does not download or discover datasets.

```bash
biotope add data/study --description "..."
biotope queue --json
```

Baker writes structural descriptions; Biotope writes them under
`.biotope/datasets/`. A directory produces one manifest for its subtree and an
annotation sidecar; a single file may contain multiple record sets such as
workbook sheets. Choose granularity deliberately. Supply provenance, creator or
license only when known. Checksums read file bytes, so large files can be costly.

Read coverage and per-file diagnostics. Distinguish described fields, partial
structure, unsupported inputs and parse failures. Do not manufacture fields for
files baker cannot describe. Record these gaps; manual format descriptions,
extracting text and preprocessing raw inputs are outside this integration workflow.

Queue status is coarse: `raw` means no field description, `processed` means
fields were described, and `mapped` means a mapping was marked defined. These
states do not certify complete metadata, correct values or an executable graph.

Regenerate directory metadata with `biotope add <directory> --rebake`; for an
individual file use `biotope add <file> --force`. Review mapping references. Do not alter source payloads to make a mapping pass.

### 3. Capture intent and author mappings

Use flags for intent; bare `biotope map` opens the human wizard.

```bash
biotope map --purpose "The agreed research question" --entity gene --entity disease \
  --relation gene_associated_with_disease
biotope map inspect .biotope/datasets/data/study.jsonld --json
biotope map scaffold .biotope/datasets/data/study.jsonld
# Edit mappings/study.mapping.yaml.
biotope map preview --json
```

Read [mapping.md](references/mapping.md) for the existing mapping grammar.
Bind only declared record sets and fields. Prefer each record set's `id` over its
display name; names may collide across sheets or files. Nested fields, container
paths, shapes and descriptions are metadata, not evidence about source values.
Inspection has no row samples.

Preserve the user's purpose and schema. Ask about ambiguous identifiers or
unsupported relations. Defer a relation with `map defer-relation` when that
reflects an agreed gap; do not erase a requirement to make checks pass.

### 4. Check and report, then stop

`biotope map preview --json` checks all project mappings; an explicit mapping
path checks one. Read `unresolved_slots`, `deferred_slots`, `findings`, and the
proposed schema. Deferred relations are acknowledged gaps, not resolved bindings;
they do not fail structural checks on their own.
Errors or partially filled bindings return exit code 1. Empty stubs are inactive
in the existing model and can pass with no schema. Compare resolved slots with
project intent; review warnings too.

A passing result covers metadata and definitions only. It does not validate
source values, transform execution, joins or scientific correctness. Record unresolved
choices and limitations alongside the mapping artifacts. Project-owned loading
and graph construction are later work; do not run build/view or create loaders.

Read [reliability.md](references/reliability.md) for identity and evidence limits.

## Supporting commands

- `status`, `queue`, `mark`: metadata and workflow state.
- `annotate`, `config`: annotations and metadata validation configuration.
- `add`, `mv`, `rm`, `check-data`: tracking and checksum checks.
- `commit`, `log`, `push`, `pull`: metadata version control. Publish only when authorized.

Use CLI commands to maintain managed metadata and provenance. Keep mapping YAML
and notes understandable to the researcher who will review them.
