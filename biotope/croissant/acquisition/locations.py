"""Path resolution for content URLs inside biotope-tracked Croissant manifests.

A biotope project stores Croissant manifests under ``.biotope/datasets/`` at
paths that mirror the original data location (e.g. data at
``<root>/data/raw/opentargets/`` → manifest at
``.biotope/datasets/data/raw/opentargets.jsonld``). Within those manifests,
``contentUrl`` / FileSet ``includes`` values are relative to the *original*
data directory, not to where the manifest lives. So a single source of truth
for "given a manifest path, where is its data root" keeps the wizard preview
and the generated build adapter in agreement.
"""

from __future__ import annotations

from pathlib import Path


def infer_datasets_location(croissant_path: str | Path) -> Path | None:
    """Return the directory ``contentUrl``/``includes`` values resolve against.

    For a manifest at ``<root>/.biotope/datasets/<rel>.jsonld`` the data root
    is ``<root>/<rel>`` (the parallel path in the actual data tree). When that
    directory doesn't actually exist on disk we fall back to the biotope
    project root, which is the next-most-useful base. For manifests outside
    ``.biotope/datasets/`` we return the manifest's own parent directory,
    matching the plain-Croissant convention. Remote (``http(s)://``) manifests
    return ``None`` — they have no on-disk root to anchor against.

    Examples
    --------
    >>> infer_datasets_location("/proj/.biotope/datasets/data/raw/opentargets.jsonld")
    PosixPath('/proj/data/raw/opentargets')   # if that directory exists

    >>> infer_datasets_location("https://example.com/dataset.jsonld") is None
    True
    """
    path_str = str(croissant_path)
    if path_str.startswith(("http://", "https://")):
        return None
    path = Path(path_str).resolve()
    for parent in path.parents:
        if parent.name == "datasets" and parent.parent.name == ".biotope":
            biotope_root = parent.parent.parent
            try:
                rel = path.relative_to(parent).with_suffix("")
            except ValueError:
                return biotope_root
            data_dir = biotope_root / rel
            if data_dir.exists():
                return data_dir if data_dir.is_dir() else data_dir.parent
            return biotope_root
    return path.parent
