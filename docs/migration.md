# Migrating to Biotope 0.9

Biotope 0.9 replaces the YAML mapping engine with typed Python graph projects.
Metadata tracking, annotation commands and purpose capture remain available.

## Graph projects

| Earlier workflow                                  | Biotope 0.9                                                 |
| ------------------------------------------------- | ----------------------------------------------------------- |
| YAML mapping files and interactive mapping wizard | Python topology, loaders, mappings and an explicit pipeline |
| `biotope map scaffold` and `biotope map preview`  | `biotope graph scaffold`, then `biotope graph check`        |
| `biotope build`                                   | `biotope graph build --out <new-run-directory>`             |
| Mapping and alignment proposals                   | Project-owned choices recorded in Python and metadata       |

There is no automatic conversion of existing mappings. Keep them as a reference,
review the intended identities and transformations, and implement a Python
workspace using the [typed graph guide](mapping.md). The [tutorial](tutorial.md)
shows a complete project.

Install `biotope[graph]` for graph checking and export. The published package
resolves croissant-baker from PyPI; remove development-only sibling-directory
overrides from your own environment when moving to the public release.

## Sources and commands

`biotope add` describes local sources through croissant-baker. Review and curate
those descriptions before generating source records. Each top-level record set
gets its own Python source package; project loaders implement physical access.

The earlier `discover`, `search`, `get`, `read`, `view`, `benchmark`,
`propose-mapping` and `propose-alignment` commands have been removed.
Use external tools for discovery or download and established format libraries
inside your project loaders.

`biotope map --purpose`, `--entity` and `--relation` retain research requirements.
Bind those requirements to topology concepts or record explicit deferrals in the
pipeline. They do not define an executable mapping by themselves.

See [commands](commands.md) for the current CLI and use `biotope --help` to check
the commands available in your installed version.
