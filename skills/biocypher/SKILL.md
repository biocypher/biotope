---
name: biocypher
description: Standalone BioCypher knowledge-graph ETL — adapters, schema_config.yaml, biocypher_config.yaml, Neo4j/CSV/PostgreSQL/RDF export, write_schema_info. Not for typed Biotope projects, which own their schema in Python.
---

# BioCypher: build a knowledge graph

BioCypher is a Python library for ontology-grounded KG construction. Three pieces: **adapters** (data in), **schema_config.yaml** (what the graph means), **biocypher_config.yaml** (where it goes).

**Check which project this is first.** If the repository has a `graph/` workspace with `topology/` and `pipelines/build_graph.py`, it is a typed Biotope project: Python topology is the schema authority, Biotope generates `schema_config.yaml` and drives the exporter, and the work belongs to the biotope-croissant skill. Writing an adapter or hand-editing the generated schema there creates a second, conflicting schema. Everything below applies to separately managed BioCypher projects.

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

Read [schema-config.md](./references/schema-config.md) before step 3. Read [outputs.md](./references/outputs.md) for step 4, import scripts and `write_schema_info()`.

## Adapters

Yield tuples — BioCypher maps `_type` via `input_label` in the schema:

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

`BioCypher()` reads `biocypher_config.yaml` from the working directory or `config/`. Override paths through constructor arguments.

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

## Small graphs and agent prototyping

`create_workflow()` builds an in-memory graph with JSON export and no DBMS. See [outputs.md](./references/outputs.md). Not for large ETL.

## Verify

After export, check file counts and read a sample of the CSVs, or run an import dry-run. **Compare expected against actual edge counts.** A silent drop usually means an id-namespace mismatch at the adapter layer, where the endpoint an edge names was never written as a node.
