# Use the result

Each build writes the graph and the files that explain it to `graph/build/`. Share these files with the graph: the meaning of each value is in `schema_config.yaml`, and its source is in `provenance.json`.

## What a build writes

- `biocypher/`: the graph as Neo4j import files, a header and a data file per node and edge type, and the import script `neo4j-admin-import-call.sh`.
- `graph.sqlite`: the graph as one SQLite file, instead of `biocypher/`, when the build ran with `--format sqlite`.
- `schema_config.yaml`: every node and edge type with its properties and their descriptions.
- `provenance.json`: the source rows behind every node and edge.
- `run.json`: the run record, with the purpose, the selected and excluded sources, the excluded records per rule, the counts, and the versions of the code, data and libraries.

A build replaces `graph/build/` only when it succeeds. A failed build keeps the previous graph and writes `graph/build/last_failure.json`.

## Load the graph into Neo4j

Stop a running Neo4j database (if present), then run the import script from the Neo4j installation folder:

```bash
cd /path/to/neo4j
bash /path/to/project/graph/build/biocypher/neo4j-admin-import-call.sh
```

The script replaces the database `neo4j` with the graph. Start Neo4j again and query it with Cypher. The Neo4j manual describes the [import tool](https://neo4j.com/docs/operations-manual/current/tools/neo4j-admin/neo4j-admin-import/).

## Query the SQLite file

Ask the agent to build with `--format sqlite`, or run `uv run --project graph biotope graph build --format sqlite`. Each node and edge type is a table, and each edge table has `source` and `target` columns that reference node tables. In the [tutorial](tutorial.md) graph, this lists each airline at SFO with its role:

```sql
SELECT Airline.name, AirlineRoleAtAirport.role
FROM AirlineRoleAtAirport
JOIN Airline ON Airline.id = AirlineRoleAtAirport.source
WHERE AirlineRoleAtAirport.target = 'airport:SFO';
```

## View the topology

The metagraph viewer shows the node and edge types with their descriptions and the counts from a build:

```bash
uv run --project graph biotope graph metagraph --report graph/build/run.json
```

Open `graph/metagraph.html` in a browser. It works offline.

## Trace a value to its source

- Every node and edge has a `biotope_provenance_id`, a position in the `records` list of `provenance.json`. That record names the mappings that made it and its evidence: each source file, its version and the row or page.
- `run.json` lists the excluded sources with their reasons under `definitions.excluded_sources`, and the excluded records under `findings`, one entry per rule with a count and sample rows.
