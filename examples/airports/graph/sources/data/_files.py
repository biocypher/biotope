"""The one helper the loaders of this root share: how a file they read is cited in evidence."""

import hashlib
from pathlib import Path

from ...paths import PROJECT_ROOT


def cited(path: Path) -> tuple[str, str]:
    """Return the project-relative name and "sha256:<digest>" of the bytes a loader reads."""
    return path.relative_to(PROJECT_ROOT).as_posix(), "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
