# `biotope propose-mapping`

**Deprecated.** Thin alias for [`biotope map scaffold`](map.md). Kept for backwards compatibility; new code should call `biotope map scaffold` directly.

The old heuristic (one RecordSet → one node type, FK-shaped fields → edges) has been removed. The alias now produces an **unresolved** semantic scaffold (with one slot per `project.yaml`-declared entity/relation plus an inspector comment appendix) that a human or copilot agent then resolves via `biotope map` (wizard) or by editing the YAML directly and running `biotope map preview`.

```bash
# These are equivalent.
biotope propose-mapping <croissant>
biotope map scaffold <croissant>
```

The deprecation notice is printed on each invocation.

::: biotope.commands.propose_mapping
