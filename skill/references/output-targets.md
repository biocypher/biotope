# Output targets: choosing and configuring what the build writes

`biotope build` materialises a BioCypher project; the **format** of what
`build/create_knowledge_graph.py` writes is the BioCypher backend (`dbms:`),
chosen with `biotope build --target {csv,neo4j}`. The flag is threaded into the
generated `build/config/biocypher_config.yaml`, and both `build` and `view`
print the resolved target so the produced format is never ambiguous.

## Decide the target with the user first

The output is not one-size-fits-all, and the wrong default wastes a full
rebuild. Before building, ask what they actually need:

- **Generic CSV / tabular** (`--target csv`, the default) — plain node and edge
  CSVs in `build/biocypher-out/`. Good for inspection, DuckDB, pandas, or loading
  into whatever store the user drives themselves.
- **Neo4j bulk import** (`--target neo4j`) — emits header + part CSVs *plus* a
  ready-to-run `neo4j-admin-import-call.sh` for the fast offline
  `neo4j-admin database import`. Choose this when the user wants a Neo4j graph.
- **Other BioCypher backends** (e.g. PostgreSQL, RDF, in-memory/networkx) — not
  on the `--target` choice list. Set `dbms:` directly in
  `build/config/biocypher_config.yaml` (see below); check the BioCypher docs for
  the exact key and confirm with the user before assuming.

Don't assume Neo4j just because the project is "a knowledge graph." Plenty of
downstream uses want the CSVs.

## Configure the target

```bash
biotope build --target neo4j        # writes dbms: neo4j into the generated config
uv run python build/create_knowledge_graph.py
```

The generated `build/config/biocypher_config.yaml` looks like:

```yaml
biocypher:
  dbms: neo4j
  log_to_disk: true
  output_directory: biocypher-out
  head_ontology: null
```

`--target` covers `csv` and `neo4j`. For any other backend, or to tune ontology
settings, edit this config file directly — it's **yours to edit**: `biotope
build` only writes it when absent, so hand edits survive subsequent builds. (That
is the exception to "don't edit generated `build/` output": the *config* under
`build/config/` is editable; the generated adapters and
`create_knowledge_graph.py` are not.) Note that because `build` writes the
config only when it's absent, `--target` sets `dbms` on a *fresh* config; if one
already exists, change `dbms:` in the file to switch backends.

## Avoid duplicate / stale outputs

The generated `create_knowledge_graph.py` **purges `build/biocypher-out/` at the
start of each run** before BioCypher writes. Re-run the entry point directly; no
manual `rm -rf` needed. If you bypass the generated script and call BioCypher
yourself, clear the output directory first — BioCypher appends by default.

## Neo4j bulk-import recipe

With `dbms: neo4j` set and the script re-run, BioCypher writes per-label
`*-header.csv` + `*-part000.csv` files and `neo4j-admin-import-call.sh`. The
import itself runs against a stopped database, e.g. with the official image:

```bash
docker run --rm \
  -v "$PWD/build/biocypher-out:/import" \
  -v neo4j-data:/data \
  neo4j:5-community \
  neo4j-admin database import full neo4j \
    --skip-bad-relationships=true \
    --skip-duplicate-nodes=true \
    --overwrite-destination=true \
    /import/<files from neo4j-admin-import-call.sh>
```

Read the generated `neo4j-admin-import-call.sh` for the exact `--nodes` /
`--relationships` arguments; it lists every file with its label. **Heads-up on
`--skip-bad-relationships`:** it silently drops edges whose endpoints don't
match a node id — convenient, but it can mask the id-namespace mismatches
described in `reliability.md`. If edge counts look low after import, suspect that
before assuming the data is thin.

## Report the format honestly, and check for schema info

State the format you actually produced, and verify it before claiming it — list
`build/biocypher-out/` and confirm Neo4j files (`*-header.csv`,
`neo4j-admin-import-call.sh`) are present before telling the user "Neo4j output
is ready." A clean `csv` run does not produce a Neo4j import script; don't say it
did.

If a downstream consumer needs BioCypher's **schema info** (e.g. BioChatter for
natural-language querying), the generated entry point calls `bc.write_schema_info()`
after writing nodes and edges — look for `build/biocypher-out/schema_info.yaml`.

Orphaned-edge and compile-drop counts land in `build/biocypher-out/build_metrics.json`;
`biotope view` and `biotope benchmark` surface them when present.
