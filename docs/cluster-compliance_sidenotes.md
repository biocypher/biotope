# Annotation policy administration examples

These examples accompany [shared annotation policies](cluster-compliance.md).
They are small utilities for exploring configuration, not a complete enforcement
service.

## Try the remote server

From a Biotope checkout, with its development environment installed:

```bash
uv run --with flask python docs/examples/remote-validation-server.py
```

The example binds to `127.0.0.1:5000` and offers `basic`, `comprehensive` and
`clinical` field sets. The names describe illustrative metadata requirements;
they do not imply an external standard has been met.

In another terminal, from an initialized project with Biotope installed:

```bash
biotope config set-remote-validation --url http://127.0.0.1:5000/comprehensive/validation.yaml --no-fallback
biotope config show-validation
```

The server returns bare validation settings in the format the loader expects.
Use an organization-managed endpoint for shared deployment.

## Inspect local project configuration

The bundled checker reads `.biotope/config.yaml` and compares the configured
pattern, required fields and remote URL presence against a requirements file:

```bash
python docs/examples/cluster-compliance-checker.py \
  --project /path/to/project \
  --requirements docs/examples/cluster-requirements.json

python docs/examples/cluster-compliance-checker.py \
  --scan-dir /path/to/projects \
  --requirements docs/examples/cluster-requirements.json --json > configuration-report.json
```

Run these from the repository checkout using its environment, and replace the
project paths. `--report <file>` writes the text or JSON report to a file.
The exit status is 0 when at least one project was found and all configurations
match, and 1 for mismatches, unreadable configurations or an empty scan.

The checker uses the literal configured label. It does not fetch remote policies,
check dataset contents or enforce field values. Fields supplied only by a remote
policy are therefore absent from this local inventory. Adjust the requirements
file to the configuration you intend to inspect.

Biotope 0.9's `show-validation-pattern` display can prefix a label with `cluster-`
or `storage-` based on words in the remote URL. That display heuristic is not a
compliance result and differs from this checker's literal label comparison.

## Example files

- [Remote validation server](examples/remote-validation-server.py)
- [Configuration checker](examples/cluster-compliance-checker.py)
- [Checker requirements](examples/cluster-requirements.json)
