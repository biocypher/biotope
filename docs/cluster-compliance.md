# Cluster metadata compliance

Biotope can enforce shared metadata requirements without building a knowledge
graph. A compliant project has annotated datasets that pass its local and
remote validation rules.

## Project workflow

```bash
biotope init my-project
cd my-project

biotope config set-validation-pattern --pattern cluster-strict
biotope config set-remote-validation \
  --url https://cluster.example.com/validation/cluster-strict

biotope add data/
biotope annotate apply data/ \
  --set creator="Jane Doe" \
  --set license="CC-BY-4.0"
biotope annotate validate --jsonld .biotope/datasets/data.jsonld
biotope status --detailed
```

Use `biotope queue` as the annotation worklist. Baker-supported files usually
become `processed`; unsupported or incomplete files remain `raw`.
`biotope mark <dataset> processed` can override status after manual review.

The graph commands (`map`, `build`, `view`, and `propose-alignment`) are
optional for compliance-only projects.

## Project boundaries

Create one biotope project per experiment, dataset, or collaboration. The
project root must contain its data: `biotope add` rejects paths and symlinks
that resolve outside the project.

For shared storage, prefer:

```text
/cluster/projects/<user>/<experiment>/
├── .biotope/
├── data/
└── pyproject.toml
```

Each project then has its own owner, validation policy, and compliance result.

## Administrator setup

1. Publish a validation document from a stable HTTPS endpoint.
2. Give users its URL and required validation pattern.
3. Run the provided compliance checker from cron or CI.

```bash
python docs/examples/cluster-compliance-checker.py \
  --scan-dir /cluster/projects \
  --requirements /etc/biotope/cluster-requirements.json \
  --report /var/log/biotope/compliance.txt
```

Example requirements:

```json
{
  "cluster_name": "Example HPC Cluster",
  "required_pattern": "cluster-strict",
  "required_fields": [
    "name",
    "description",
    "creator",
    "dateCreated",
    "distribution",
    "license",
    "project_id"
  ],
  "require_remote_validation": true
}
```

The repository includes a
[compliance checker](examples/cluster-compliance-checker.py), sample
[requirements](examples/cluster-requirements.json), and a minimal
[validation server](examples/remote-validation-server.py).

## Validation document

The remote endpoint returns YAML:

```yaml
annotation_validation:
  enabled: true
  minimum_required_fields:
    - name
    - description
    - creator
    - dateCreated
    - distribution
    - license
  field_validation:
    name:
      type: string
      min_length: 1
    creator:
      type: object
      required_keys: [name, institution]
    dateCreated:
      type: string
      format: date
    distribution:
      type: array
      min_length: 1
```

Supported rules:

- `type`: `string`, `object`, or `array`
- `min_length`: trimmed characters for strings; item count for arrays
- `required_keys`: required keys for objects
- `format: date`: ISO 8601 date

Remote and local `minimum_required_fields` are combined. Local
`field_validation` entries override remote entries for the same field.

Successful responses are cached under `.biotope/cache/validation/` for
`cache_duration` seconds (default: 3600). Force a refresh with:

```bash
biotope config clear-validation-cache
```

If the server is unavailable, `fallback_to_local: true` uses local rules.
Set it to `false` when validation must fail closed. Administrators should
monitor compliance reports either way.

## Processing unsupported data

Agents and users follow the same CLI loop:

```bash
biotope queue --json
biotope add data/report_tables.csv --derived-from data/report.pdf
biotope annotate validate \
  --jsonld .biotope/datasets/data/report_tables.jsonld
```

Keep the raw input for provenance. Add extracted, baker-supported artifacts
with `--derived-from`, then review their metadata before marking work complete.
Plugin users can run this loop with the
[`biotope-croissant` skill](plugin.md).
