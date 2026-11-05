# Biotope

--8<-- "README.md:headline"

--8<-- "README.md:handles"

## Start here

- [Get started](get-started.md): install the plugin and start a project.
- [Working with the agent](agent.md): the purpose statement, your decisions and the review.
- [Use the result](result.md): load the graph into Neo4j, query it in SQLite and trace its values.

## Limits

- Biotope does not decide which records are the same thing. You or the agent decide, and the agent records the decision.
- The checks test the structure of the graph. Review its content against the sources.
- The whole graph is held in memory during a build, so choose a scope that fits the machine.

## Versions

Biotope follows [semantic versioning](https://semver.org/): a change that breaks your project comes in a new major version. The [changelog](changelog.md) lists the changes in each release.
