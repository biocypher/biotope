# Declaring identity and precedence

Biotope merges records into entities only on the keys a project declares and on the match links its matcher writes, and takes each field from the source the project ranks first. These declarations decide which records the graph treats as one thing and which value it shows, so they are reviewed artefacts. The contracts are in the Biotope documentation page "Identity and precedence".

## Who decides what

- The user decides what identifies an entity and which source wins: which fields are keys, whether a key holds one value per entity, any matcher and its threshold, and the order of sources for each field. You propose each from the purpose and the records; the user approves.
- You decide the engineering: record IDs, the module layout, how mappings give relation endpoints, and the commands.
- **Stop and ask before any merge without a shared key.** A shared accession, DOI, ORCID or another source's record ID establishes a match. A name, symbol, label or a similarity score does not. Declaring such a field as a key, or adopting a matcher, merges without a shared accession; do neither without the user's explicit approval, and record the decision in `graph/ASSUMPTIONS.md`.

## Steps

1. Read the purpose and, for every node concept that several sources or several records describe, a sample of each source's records. List the identifiers each source carries: accessions, DOIs, ORCIDs, emails, record IDs of other sources, and IDs of B1 extracted records.
1. Propose an `Identity` per such concept in `graph/alignment/__init__.py`:
   - its keys, each a `str` or `list[str]` field of the concept, with the identifier each holds;
   - which keys are single-valued. Ask the user for each: a single-valued key keeps apart records that would give an entity two values, such as two ORCIDs, and a real person can have two;
   - a natural key, such as an accession or a DOI, when one exists, so the entity keeps it as its ID.
1. Before the first build, list every proposed key that is not an accession, such as a gene symbol, a name, a label, a symbol scoped to one table or an email a team shares. For each, say what it would merge: which sources' records it joins that no accession joins, with a count from the sample records and two examples. Ask the user to approve or drop each such key, and ask whether each key, accession or not, holds one value per entity. Build only after the user answers.
1. Propose a `Precedence` per concept and relation for each field that several sources fill: the order of sources with the reason for each place, or `combine` for a list field such as emails or symbols. A field without a declaration stops the build when sources give different values, which is the right default for a field the user has not ranked.
1. When the purpose needs matches no key gives, such as people whose only shared trait is a similar name, propose a matcher: a script in the project, such as `matchers/similar_names.py`, that reads the inputs and writes SSSOM rows with an automatic justification, such as `semapv:LexicalMatching`, to a file the project describes and loads as a source. A mapping turns each row into a `Match`. Show the user the links before adopting the matcher; this is a merge without a shared key.
1. Write the mappings: one copy per source record, whose `id` is that record's ID with a namespace, such as `roster:<record>` or `profile:<extracted record ID>`. Give relation endpoints by any key value, `<key>:<value>`, or record ID; biotope resolves them to entity IDs.
1. Run `biotope graph build` and read `run.json`'s `identity` section and `graph/build/entities.jsonl`. Check them yourself first: `merged_by_key`, which counts per key the entities that key merged; entities merged from records that should stay apart; contradictions and what was kept apart; conflicts; automatic merges; unresolved links; and relations left out under `ambiguous_endpoints`. Any count under a key that is not an accession is a merge without a shared accession.
1. Show the user, before the declarations are adopted: the declarations with the reason for each key and order; the merges per key from `merged_by_key`, naming every key that is not an accession and its count; for a sample of merged entities, their records and how they were joined; every contradiction with its key, values, entities and the records or links kept apart; the conflicts, each with every source's value and the chosen one; and every automatic merge with its justification. Revise with the user until they approve.
1. Any later change to a key, a single-valued flag, a source order or a matcher, however small, changes which records merge or which value wins: build again, show the user what changed in the merges, contradictions and conflicts, and get their approval again.

## Reading the result

- A contradiction means a record or a link would have given an entity two values of a single-valued key. Biotope keeps it apart and the build goes on; the user decides whether the key is wrong, the source is wrong or the record belongs elsewhere.
- A relation under `ambiguous_endpoints` was left out because its endpoint names several entities, which happens when only records kept apart hold that key value. Resolve the contradiction behind it, or give the endpoint by a record ID.
- A conflict means sources gave different values for a ranked field; the entity shows the first source's. Many conflicts on one field often mean the sources measure different things; ask before ranking them.
- An entity without a natural key gets a derived ID that changes when its records change. Nothing outside the build should point at it until B3 registers IDs.
