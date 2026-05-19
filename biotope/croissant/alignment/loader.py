"""Load and validate ``alignment.yaml``."""

from __future__ import annotations

from pathlib import Path

import yaml

from biotope.croissant.alignment.model import Alignment


def load_alignment(path: str | Path) -> Alignment:
    """Load and validate an ``alignment.yaml`` file."""
    data = yaml.safe_load(Path(path).read_text())
    return Alignment.model_validate(data)
