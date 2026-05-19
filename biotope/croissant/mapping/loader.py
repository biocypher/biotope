"""Load and validate a ``mapping.yaml`` file."""

from __future__ import annotations

from pathlib import Path

import yaml

from biotope.croissant.mapping.model import Mapping


def load_mapping(path: str | Path) -> Mapping:
    """Load and validate a ``mapping.yaml`` file from disk."""
    data = yaml.safe_load(Path(path).read_text())
    return Mapping.model_validate(data)


def dump_mapping(mapping: Mapping, path: str | Path) -> None:
    """Serialise a :class:`Mapping` to ``path`` as YAML."""
    Path(path).write_text(
        yaml.safe_dump(
            mapping.model_dump(by_alias=True, exclude_defaults=False),
            sort_keys=False,
        ),
    )
