# Working with the agent

You decide what the graph is for and make the choices that change its answers. The agent describes the data, writes and runs the code, and reports what it did.

## Write the purpose statement

The purpose statement says who uses the graph, for which tasks, and the typical questions they ask. The agent drafts it from your first message and a first look at the data. You correct the draft, and the agent records it with `biotope map --purpose`. The node and edge types follow from the questions, and the agent checks later choices against them. The agent asks you questions until you agree on the purpose.

Example for organisation management: "Institute staff and management use the graph to find who works on what. Typical questions: which groups work on single-cell methods? Who has published with a given partner institute? Which research best suits an upcoming grant?"

For biomedical research: "The target-discovery team ranks genes as drug targets for liver fibrosis. Typical questions: which genes change expression in fibrotic tissue in at least two studies? Which of them have a known compound?"

## What you get back

- The graph in `graph/build/`. [Use the result](result.md) explains each file.
- A hand-over report: the sources selected and excluded, with reasons; the records excluded, per rule; the claims the agent checked against the sources; and the open questions.
- `graph/ASSUMPTIONS.md`, with the decisions and the open questions.

## Review the result

Biotope's checks test the structure of the graph. Agents are not good at understanding the semantics of relations and sometimes make trivial mistakes. Biotope enforces best practices and makes it hard for an agent to make technical mistakes, but always check that the final representation is sensible:

1. Read the hand-over report and `graph/ASSUMPTIONS.md`.
2. Check that the questions the Biotope agent generated from the purpose and used for testing the graph are representative.
3. Open the [metagraph viewer](result.md#view-the-topology) and check that the node and edge types can answer your questions.
4. Pick a few values you know and trace them to their sources.

## Later

When new data of the same shape arrives, ask the agent to update the graph. A change in the data's structure, such as a new column or a new table, needs the agent.
