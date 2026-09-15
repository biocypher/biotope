# Shared annotation policies

A project can combine local annotation requirements with rules served from a
remote YAML file. This supports shared metadata conventions across a group or
cluster. These settings assess metadata fields; they do not certify a dataset's
scientific, legal or institutional compliance.

## Set local requirements

From an initialized Biotope project:

```bash
biotope config set-validation --field project_id --type string --min-length 1
biotope config set-validation --field license --type string --min-length 5
biotope config set-validation-pattern --pattern cluster-strict
biotope config show-validation
```

`set-validation-pattern` assigns a label. It does not install a preset or add
validation rules. Configure required fields separately.

Local settings live under `annotation_validation` in `.biotope/config.yaml`.
Supported field rules include string, object and array types, minimum lengths,
required object keys. The `dateCreated` field is checked as an ISO date. Arbitrary JSON Schema keywords such as
`pattern` are not enforced.

## Serve remote requirements

A remote document contains the validation settings at its **top level**:

```yaml
enabled: true
minimum_required_fields:
  - name
  - description
  - creator
  - dateCreated
  - distribution
  - project_id
field_validation:
  name:
    type: string
    min_length: 1
  description:
    type: string
    min_length: 20
  creator:
    type: object
    required_keys: [name]
  dateCreated:
    type: string
  distribution:
    type: array
    min_length: 1
  project_id:
    type: string
    min_length: 1
```

The remote file has no `annotation_validation` wrapper. That wrapper belongs only
in the local project configuration.

Host this document at a URL your projects can read. Replace the example URL below
with that address:

```bash
biotope config set-remote-validation --url https://example.org/validation.yaml --no-fallback
biotope config show-remote-validation
biotope config show-validation
```

Required fields are the union of local and remote lists. A local rule for a field
replaces that field's remote rule, and other local settings take precedence.
A centrally served file therefore supplies shared defaults; it does not prevent
local overrides.

Remote responses are cached for 3,600 seconds by default. Set `--cache-duration`
to change this. Without `--no-fallback`, unavailable remote settings fall back to
local configuration. To fetch a changed policy on the next load:

```bash
biotope config clear-validation-cache
biotope config show-validation
```

## Review annotation status

Describe selected local files with `biotope add <path>`, then edit the metadata
with the `annotate` commands. Use `biotope status --detailed` to inspect annotation
issues for tracked datasets. Status is a report, not a failing CI gate.

The related commands check different things:

| Command or example                          | What it checks                                                             |
| ------------------------------------------- | -------------------------------------------------------------------------- |
| `biotope status --detailed`                 | Annotation status under the effective field requirements                   |
| `biotope annotate validate --jsonld <file>` | Croissant validation through the external `mlcroissant` CLI                |
| `biotope commit`                            | JSON readability, with warnings for missing dataset type or name           |
| `biotope queue`                             | Coarse curation state based on field descriptions and manual mapping state |
| Bundled configuration checker               | Locally configured labels, required fields and remote URL presence         |

Neither `annotate validate` nor `commit` enforces the shared annotation policy as
a CI gate. Queue states also do not certify annotation completeness.

For a local server and configuration inventory example, see the
[administration notes](cluster-compliance_sidenotes.md).
