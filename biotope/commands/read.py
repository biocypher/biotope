"""``biotope read`` — NLP ingestion and health-check entry point.

v1 promise: the canonical way to ingest unstructured text into the project's
graph and the entry point for sanity checks before/after a build. Currently a
passthrough that echoes the input; future scope is wiring into
``epistemic-agent``'s synthesis loop.
"""

from __future__ import annotations

import click


@click.command()
@click.option(
    "--text",
    "-t",
    type=str,
    help="Text to extract knowledge from",
    required=False,
)
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True, dir_okay=False, path_type=str),
    help="File to extract knowledge from",
    required=False,
)
def read(text: str | None, file: str | None) -> None:
    """
    Extract knowledge from input text or file using NLP.

    Args:
        text: Input text to process
        file: Input file to process

    Raises:
        click.UsageError: If neither --text nor --file is provided.

    """
    if text is None and file is None:
        msg = "Either --text or --file must be provided"
        raise click.UsageError(msg)

    if file is not None:
        with open(file) as f:
            text = f.read()

    if text is not None:  # This will now be true in both cases
        result = extract_knowledge(text)
        click.echo(result)


def extract_knowledge(text: str) -> str:
    """
    Extract knowledge using NLP and other methods.

    Args:
        text: Input text to process

    Returns:
        Extracted knowledge (currently just returns input)

    """
    return f"Extracted knowledge: {text}"
