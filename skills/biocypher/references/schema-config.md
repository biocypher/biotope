# Schema configuration essentials

`schema_config.yaml` defines which entities and relationships enter the graph and how adapter `input_label` values map to ontology-grounded types.

## Adapter tuple contract

**Nodes** — yield `(_id, _type, _props)`:

```python
yield ("P04637", "protein", {"name": "TP53", "function": "tumor_suppressor"})
```

**Edges** — yield `(_id, _source, _target, _type, _props)` (`_id` may be `None`):

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

## Rules

- Top-level keys: lower sentence case (`protein`, `small molecule`). File/Neo4j labels become PascalCase automatically.
- `source` / `target` on edges pin direction — critical for downstream Cypher generation (BioChatter uses these).
- Omit `preferred_id` when no suitable namespace exists; a generic `id` property is created.
- `label_as_edge: PERTURBS` overrides the default edge label in property-graph outputs.

Full reference: https://biocypher.org/reference/schema-config/
