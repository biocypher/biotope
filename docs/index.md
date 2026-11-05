# Biotope

--8<-- "README.md:headline"

--8<-- "README.md:handles"

## Start here

- [Get started](get-started.md): install the plugin and start a project.
- [Working with the agent](agent.md): the purpose statement, your decisions and the review.
- [Use the result](result.md): load the graph into Neo4j, query it in SQLite and trace its values.

## Limits

- Biotope never decides by itself which records are the same thing. You or the agent decide, and the decision is recorded.
- The checks test the structure, not whether the content is right. Review the content against the sources.
- The whole graph is held in memory while it is built, so choose a scope that fits the machine.

## Versions

Biotope follows [semantic versioning](https://semver.org/): a change that breaks your project comes only in a new major version. The [changelog](changelog.md) lists the changes in each release. Biotope grows from real projects: an institute's register of who works on what, and biomedical graphs.
