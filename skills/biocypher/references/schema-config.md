# Schema configuration essentials

Read this before authoring `schema_config.yaml`, which decides which entities and relationships enter the graph and how adapter `input_label` values map to ontology-grounded types.

## Adapter tuple contract

**Nodes** — yield `(_id, _type, _props)`:

```python
yield ("P04637", "protein", {"name": "TP53", "function": "tumor_suppressor"})
```

**Edges** — yield `(_id, _source, _target, _type, _props)`, where `_id` may be `None`:

```python
yield (None, "P04637", "P15056", "interaction", {"score": 0.9})
```

`_type` must match `input_label` in the schema entry.

## Minimal node entry

```yaml
protein:
  represented_as: node
  preferred_id: uniprot
  input_label: protein
  properties:
    name: str
    function: str
```

## Minimal edge entry

```yaml
protein protein interaction:
  is_a: pairwise molecular interaction
  represented_as: edge
  input_label: interaction
  source: protein
  target: protein
  properties:
    score: float
```

## Top-level keys are lower sentence case

Write `protein`, `small molecule`. File and Neo4j labels become PascalCase automatically.

## `source` and `target` pin edge direction

Without them, downstream query generation has nothing to constrain direction against and will reverse edges.

## Omit `preferred_id` when no namespace fits

A generic `id` property is created instead. Inventing a namespace to fill the field asserts an identity the data does not carry.

## `label_as_edge` overrides the property-graph edge label

For example `label_as_edge: PERTURBS`. It changes the exported label only, not the schema entry's identity.

Full reference: https://biocypher.org/reference/schema-config/
