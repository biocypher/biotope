# Output formats and finalisation

Read this when choosing a backend, configuring `biocypher_config.yaml`, or importing an offline export.

Configuration lives in `biocypher_config.yaml` in the project root or `config/`. Core keys under `biocypher:`:

```yaml
biocypher:
  dbms: neo4j              # neo4j | postgres | csv | networkx | rdf | …
  schema_config_path: config/schema_config.yaml
  offline: true
  output_directory: biocypher-out
  head_ontology:
    url: https://github.com/biolink/biolink-model/raw/v3.2.1/biolink-model.owl.ttl
    root_node: entity
```

DBMS-specific blocks (`neo4j:`, `postgres:`, …) hold connection settings, the data `file_format`, and the import delimiters — `csv_column_delimiter`, `csv_array_delimiter` (default `;`) and `csv_string_quote_character` for Neo4j.

## Build loop

```python
from biocypher import BioCypher

bc = BioCypher()
bc.write_nodes(node_generator())
bc.write_edges(edge_generator())
bc.write_import_call()      # offline: neo4j-admin script, etc.
bc.write_schema_info()      # optional: schema_info.yaml for NL query tools
```

Repeated `write_nodes` and `write_edges` calls deduplicate within one `BioCypher` instance. `write_schema_info()` runs **after** all nodes and edges are written, and only on offline or in-memory backends. For online Neo4j, install `biocypher[neo4j]`, set `offline: false`, and use `add_*` or driver-backed writes.

## Neo4j offline import (BioCypher 0.17)

With `dbms: neo4j` and `offline: true`, the data format follows `neo4j.file_format`, which **defaults to `parquet`**. Set it to `csv` unless the target Neo4j release accepts Parquet import. CSV writes `*-header.csv` and `*-part*.csv`; Parquet writes `*-part*.parquet` and no headers. Either way you get `neo4j-admin-import-call.sh`. Import against a **stopped** database, and read the generated script for the exact `--nodes` and `--relationships` arguments.

Review the generated import script before running it. Its paths must match the
filesystem visible to `neo4j-admin`, and its flags must be supported by the target
Neo4j version. Import into the intended stopped database, then compare node and
edge counts with the export. Skipping bad relationships or duplicate nodes can
hide missing endpoints or identity problems; investigate those differences.

## Other backends

`csv` and tabular output produce plain files for DuckDB, pandas or a custom loader. For `postgres`, `sqlite`, `arangodb` and `rdf`, see the [output reference](https://biocypher.org/BioCypher/reference/outputs/).

## Agent API for small in-memory graphs

`create_workflow()` offers an in-memory API with JSON export. Assess memory use
for the selected data; there is no general node-count limit that fits every graph:

```python
from biocypher import create_workflow

kg = create_workflow("my_graph", validation_mode="none")
kg.add_node("TP53", "protein", name="TP53")
kg.add_node("BRAF", "protein", name="BRAF")
kg.add_edge("i1", "interaction", "TP53", "BRAF", confidence=0.8)
kg.save("graph.json")
```

This example saves JSON and disables schema validation. Use the adapter-based
`BioCypher()` interface when you need database-specific export.
