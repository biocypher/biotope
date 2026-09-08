# Describe local data and define a mapping

This example uses a tiny local CSV so you can inspect the expected structure.
Use the environment where Biotope and the updated croissant-baker are installed.
For an unreleased checkout, install both editable packages into the same virtual
environment; keep that environment active throughout.

## Initialize and describe

```bash
biotope init mapping-demo --no-prompt
cd mapping-demo
cat > data/genes.csv <<'CSV'
gene_id,symbol
ENSG00000141510,TP53
ENSG00000146648,EGFR
CSV
biotope add data/genes.csv --description "Two gene identifiers for a mapping demonstration"
biotope queue
biotope map inspect .biotope/datasets/data/genes.jsonld
biotope map inspect .biotope/datasets/data/genes.jsonld --json
```

The manifest describes `gene_id` and `symbol`. Inspection reports structure,
not row samples. Read the ingestion summary to see whether fields were described
and whether baker reported limitations. Single files and directories are both
supported; start with explicit, bounded paths on large datasets.

## State purpose and author a mapping

```bash
biotope map --purpose "Describe the supplied gene identifiers and symbols" --entity gene
biotope map scaffold .biotope/datasets/data/genes.jsonld
```

Edit `mappings/genes.mapping.yaml`. Use the record-set `id` from inspection for
`record_set` (in this example, normally `genes`). Keep the scaffold's `croissant`
reference, and replace the entity's unresolved binding:

```yaml
entities:
  gene:
    record_set: genes
    scan: row
    id: gene_id
    properties:
      symbol: symbol
relations: {}
```

The identifier choice is explicit; structural checks cannot prove uniqueness or
scientific suitability. See [Mapping reference](mapping.md) for relations,
nested fields, selectors and intentional deferrals. For human interactive
editing, run `biotope map`.

## Check and stop

```bash
biotope map preview --json
biotope map preview
biotope status
```

The definition should have no unresolved slots or error findings. Exit code 1
means errors or unfinished bindings need attention. Passing checks cover
metadata and definitions, not values, joins, transformations or graph results.
Save the mapping and document remaining choices. This workflow ends here.

If the source changes, re-run `biotope add data/genes.csv --force`, inspect the
new manifest and review its mappings. `check-data` checks recorded checksums;
it reads bytes and can be expensive for large files. Neither command performs
scientific validation.
