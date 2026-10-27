"""Atomic writes of generated artifacts."""

from biotope.graph.sources import write_text_atomic


def test_atomic_artifacts_respect_creation_and_existing_permissions(tmp_path):
    ordinary, artifact = tmp_path / "ordinary", tmp_path / "artifact"
    ordinary.write_text("ordinary")
    write_text_atomic(artifact, "new")
    assert artifact.stat().st_mode & 0o777 == ordinary.stat().st_mode & 0o777
    artifact.chmod(0o640)
    write_text_atomic(artifact, "replacement")
    assert artifact.stat().st_mode & 0o777 == 0o640
    assert artifact.read_text() == "replacement"
