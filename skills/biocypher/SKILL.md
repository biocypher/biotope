---
name: biocypher
description: Build knowledge graphs with BioCypher — adapters, schema_config.yaml, biocypher_config.yaml, and multi-backend export (Neo4j, CSV, PostgreSQL, RDF). Use for standalone KG ETL pipelines, writing schema_info.yaml, Neo4j bulk import, or tuning dbms/output settings. Trigger on BioCypher, schema_config, biocypher_config, write_nodes, write_edges, knowledge graph construction, Biolink schema, or graph database export.
---

# BioCypher: build a knowledge graph

BioCypher is a Python library for ontology-grounded KG construction. Three pieces: **adapters** (data in), **schema_config.yaml** (what the graph means), **biocypher_config.yaml** (where it goes).

```bash
pip install biocypher
pip install "biocypher[neo4j]"   # only if using Neo4j online mode
```

Project template: https://github.com/biocypher/project-template

## Workflow

```
1. Define scope (entities, relations, ontologies)
2. Write adapters → yield node/edge tuples
3. Author schema_config.yaml (input_label ↔ ontology types)
4. Configure biocypher_config.yaml (dbms, paths)
5. BioCypher().write_nodes / write_edges → export
```

Read `references/schema-config.md` before authoring schema. Read `references/outputs.md` for dbms choice, import scripts, and `write_schema_info()`.

## Adapters

Yield tuples — BioCypher maps `_type` via `input_label` in schema:

```python
def node_generator():
    for row in rows:
        yield (row["uniprot_id"], "protein", {"name": row["name"]})

def edge_generator():
    for row in edges:
        yield (None, row["src"], row["tgt"], "interaction", {"score": row["score"]})
```

Reuse existing adapters: https://github.com/orgs/biocypher/projects/3/views/2

## Run

```python
from biocypher import BioCypher

bc = BioCypher()
bc.write_nodes(node_generator())
bc.write_edges(edge_generator())
bc.write_import_call()
bc.write_schema_info()   # optional — for NL query tools
```

`BioCypher()` reads `biocypher_config.yaml` from cwd or `config/`. Override paths via constructor args if needed.

## Config essentials

```yaml
# biocypher_config.yaml
biocypher:
  dbms: neo4j
  schema_config_path: config/schema_config.yaml
  offline: true
  output_directory: biocypher-out
  head_ontology:
    url: https://github.com/biolink/biolink-model/raw/v3.2.1/biolink-model.owl.ttl
    root_node: entity
```

```yaml
# schema_config.yaml (minimal)
protein:
  represented_as: node
  preferred_id: uniprot
  input_label: protein
```

## Small graphs / agent prototyping

`create_workflow()` — in-memory, JSON export, no DBMS. See `references/outputs.md` "Agent API". Not for large ETL.

## Verify

After export, check file counts and spot-read CSVs or run import dry-run. For Neo4j, compare expected vs actual edge counts — silent drops often mean id namespace mismatches at the adapter layer.

## Optional next step

With `schema_info.yaml` and a loaded graph database, **ask the user** before loading the **biochatter** skill for natural-language querying.
