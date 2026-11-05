# Working with the agent

You decide what the graph is for and the choices that change its answers. The agent does the rest: it describes the data, writes and runs the code, and reports what it did and what it left open.

## Write the purpose statement

The purpose statement says who uses the graph, for which tasks, and the typical questions they ask. The agent drafts it from your first message and a first look at the data. You correct the draft, and the agent records it with `biotope map --purpose`. The node and edge types follow from the questions, and every later choice is checked against them.

- **An organization:** "Institute staff and management use the graph to find who works on what. Typical questions: which groups work on single-cell methods? Who has published with a given partner institute? Which projects end this year?"
- **Biomedical research:** "The target-discovery team ranks genes as drug targets for liver fibrosis. Typical questions: which genes change expression in fibrotic tissue in at least two studies? Which of them have a known compound?"

## What the agent asks you

The agent stops and asks when a choice changes the answers:

- Whether two things are one, such as a preprint and its journal version, or two records from different sources with the same name. Biotope never merges records by itself.
- Which reading of a value to use, when a table allows two and they keep different records.
- The creator and license of each dataset. The agent writes none that nobody gave.
- For [documents](extraction.md): which services may read them and how API keys are supplied, and whether the fields it proposes to extract are the right ones.

It records each answer in `graph/ASSUMPTIONS.md` or in the dataset's annotation file. When nobody can answer, it takes a safe default, such as keeping two records apart, and lists the question in `graph/ASSUMPTIONS.md`.

## IDs stored elsewhere

Each build makes the graph from scratch, so an ID stays the same only when it comes from the data. When your IDs already live in another system, such as an Airtable base or a registry, give the agent that system's export as a source. The graph reads the IDs back, and only new things get new IDs.

## What you get back

- The graph in `graph/build/`. [Use the result](result.md) explains each file.
- A hand-over report: the sources selected and excluded, with reasons; the records excluded, per rule; the claims the agent checked against the sources themselves; and the open questions.
- `graph/ASSUMPTIONS.md`, with the decisions and the open questions.

## Review the result

Biotope's checks test the structure, not whether the content is right: a record that was wrongly left out passes every check. Review the content yourself:

1. Read the hand-over report and `graph/ASSUMPTIONS.md`.
2. Open the [metagraph viewer](result.md#view-the-topology) and check that the node and edge types can answer your questions.
3. Pick a few values you know and trace them to their sources.

To review the code the agent wrote, read the [skill's references](https://github.com/biocypher/biotope/tree/main/skills/biotope-croissant/references): they document the contracts it writes against.

## Later

When new data of the same shape arrives, ask the agent to rebuild the graph, or run the commands in [Your project](project.md#new-data) yourself. A change in the data's structure, such as a new column or a new table, needs the agent.

## Privacy

The coding agent reads your files. Extractors send documents only to the services you approve, and API keys stay in environment variables.
