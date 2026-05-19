# `biotope view`

Inspect a project at-a-glance. Always prints the project's competence questions (`purpose`, `required_entities`, `required_relations`) so the user can see what's hidden inside `.biotope/`. Then prints node and edge counts for the most recent `biotope build` output, if one exists.

Pass `--no-header` to suppress the project summary. Future scope: sample queries, schema diff against `.biotope/config.yaml`.

::: biotope.commands.view
