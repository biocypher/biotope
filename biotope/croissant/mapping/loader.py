"""Load and validate a ``mapping.yaml`` file."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from biotope.croissant.mapping.model import Mapping


def load_mapping(path: str | Path) -> Mapping:
    """Load and validate a semantic ``mapping.yaml`` file from disk.

    Raises :class:`ValueError` with a clear regeneration message when the file
    still uses the legacy ``nodes``/``edges`` schema.
    """
    data = yaml.safe_load(Path(path).read_text())
    if data is None:
        data = {}
    try:
        return Mapping.model_validate(data)
    except ValidationError as exc:
        # Pydantic wraps the legacy-rejection ValueError from the validator;
        # re-raise the bare message so users see the regeneration hint cleanly.
        for err in exc.errors():
            ctx = err.get("ctx") or {}
            err_obj = ctx.get("error") if isinstance(ctx, dict) else None
            if isinstance(err_obj, ValueError) and "Legacy" in str(err_obj):
                raise ValueError(str(err_obj)) from exc
        raise


def dump_mapping(mapping: Mapping, path: str | Path) -> None:
    """Serialise a :class:`Mapping` to ``path`` as YAML."""
    from biotope.croissant.mapping.render import render_mapping_yaml

    Path(path).write_text(render_mapping_yaml(mapping))
