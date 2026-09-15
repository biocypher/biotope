# Command output

Keep command mechanics separate from structured results and their presentation.
Use the same evidence for human and JSON output; renderers must not read source
payloads or reconstruct facts from messages.

## Human output

Lead with the target and operation, then a compact outcome. Group successful
checks. Show every actionable warning, error, deferral and blocked check with
its subject and explanation. Do not require `--verbose` to discover problems.

Use a fixed status column and wrapping content, as in `_add_output.py`. Preserve
full paths and identifiers, including spaces and literal markup. Align wrapped
lines with their content column. Use restrained colour plus explicit status
words; avoid wide tables, decorative panels and repetitive next-step lists.

```text
Check  graph/
OK     Sources · topology · requirements
FAIL   Python
       graph/mappings/study.py:84:17
       Expected StudyId; received GeneId.
```

Show a spinner immediately during slow work when totals are unknown. Keep live
diagnostics above progress, and avoid printing them twice. Disable animation
on non-terminal output and in JSON mode. Respect `NO_COLOR`. State the operation's
scope once: definition checking, execution without export, or execution/export.

## JSON output

Use explicit `--json`, not agent detection. Write one versioned document to
stdout, including operational failures. Keep logs, incidental dependency output
and progress on stderr. Preserve stable finding codes, exact references, counts,
denominators, locations and skipped reasons. Examples may be bounded, with
truncation explicit; distinct diagnostics must remain complete.

Do not infer JSON from rendered text. Exit nonzero for operational/integrity
errors; advisory warnings alone succeed. Invalid command syntax may use Click's
ordinary usage errors. Missing measurements are not zero or successful checks.

## Verification and scope

Test meaningful output scenarios: narrow terminals, long paths, literal markup,
noisy imports, redirected output and a JSON failure. Check information and
layout invariants instead of maintaining large snapshots or trivial cases.
Apply these standards to new and changed commands; do not rewrite unrelated
commands to satisfy this file.

References: [uv output controls](https://docs.astral.sh/uv/reference/cli/),
[pnpm reporters](https://pnpm.io/cli/install#--reportername),
[Homebrew colour controls](https://docs.brew.sh/Manpage).
