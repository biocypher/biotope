"""Tests for `infer_datasets_location` — the single source of truth used by
both the wizard preview and the generated build adapter to anchor relative
``contentUrl`` / FileSet ``includes`` values inside biotope-tracked manifests.
"""

from __future__ import annotations

from pathlib import Path

from biotope.croissant.acquisition import infer_datasets_location


def test_biotope_managed_manifest_resolves_to_existing_parallel_data_dir(tmp_path: Path) -> None:
    """Manifest under `.biotope/datasets/<rel>.jsonld` with matching data dir
    returns `<root>/<rel>` — the base for relative `includes` globs."""
    root = tmp_path
    (root / "data" / "inputs" / "opentargets").mkdir(parents=True)
    manifest = root / ".biotope" / "datasets" / "data" / "inputs" / "opentargets.jsonld"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}")

    location = infer_datasets_location(str(manifest))

    assert location == (root / "data" / "inputs" / "opentargets").resolve()


def test_biotope_managed_falls_back_to_project_root_when_data_dir_missing(
    tmp_path: Path,
) -> None:
    """If the parallel data dir doesn't exist on disk, fall back to the biotope
    project root so the resolver still anchors somewhere sensible."""
    root = tmp_path
    manifest = root / ".biotope" / "datasets" / "ghost.jsonld"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}")

    location = infer_datasets_location(manifest)

    assert location == root.resolve()


def test_standalone_manifest_uses_its_own_parent(tmp_path: Path) -> None:
    """A manifest outside `.biotope/datasets/` resolves against its own dir."""
    manifest = tmp_path / "standalone.croissant.json"
    manifest.write_text("{}")

    location = infer_datasets_location(manifest)

    assert location == tmp_path.resolve()


def test_remote_manifest_returns_none() -> None:
    """`http(s)://` manifests have no on-disk root; callers handle None."""
    assert infer_datasets_location("https://example.com/x.jsonld") is None
    assert infer_datasets_location("http://example.com/x.jsonld") is None
