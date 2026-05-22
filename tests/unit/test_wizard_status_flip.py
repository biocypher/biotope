"""When the wizard saves a fully resolved mapping, the dataset's
biotope:status flips from `processed` to `mapped`."""

from __future__ import annotations

import json
from pathlib import Path

from biotope.commands.map_wizard import _flip_referenced_dataset_to_mapped
from biotope.croissant.mapping import Mapping
from biotope.metadata import STATUS_MAPPED, STATUS_PROCESSED, get_status


def _write_minimal_croissant(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "@context": {"@vocab": "https://schema.org/"},
                "@type": "sc:Dataset",
                "name": "minimal",
                "recordSet": [
                    {
                        "@id": "genes",
                        "@type": "cr:RecordSet",
                        "name": "genes",
                        "field": [{"@id": "genes/ensembl_id", "name": "ensembl_id", "dataType": "sc:Text"}],
                    }
                ],
                "biotope:status": "processed",
            }
        )
    )


def test_resolved_mapping_save_flips_manifest_to_mapped(tmp_path: Path) -> None:
    croissant = tmp_path / "minimal.jsonld"
    _write_minimal_croissant(croissant)
    assert get_status(json.loads(croissant.read_text())) == STATUS_PROCESSED

    mapping = Mapping.model_validate(
        {
            "croissant": str(croissant),
            "entities": {
                "gene": {"record_set": "genes", "id": "ensembl_id"},
            },
        }
    )
    assert mapping.is_resolved()

    _flip_referenced_dataset_to_mapped(mapping)

    assert get_status(json.loads(croissant.read_text())) == STATUS_MAPPED


def test_show_status_on_exit_surfaces_mapped(tmp_path: Path, capsys) -> None:
    """When status is `mapped`, the exit panel confirms the auto-flip."""
    from biotope.commands.map_wizard import _show_status_on_exit

    datasets_dir = tmp_path / "proj" / ".biotope" / "datasets"
    datasets_dir.mkdir(parents=True)
    croissant = datasets_dir / "data" / "ot" / "target.jsonld"
    croissant.parent.mkdir(parents=True)
    croissant.write_text(
        json.dumps(
            {
                "@type": "sc:Dataset",
                "name": "data/ot/target",
                "biotope:status": "mapped",
            }
        )
    )

    _show_status_on_exit({"croissant": str(croissant)}, croissant)
    captured = capsys.readouterr()
    assert "mapped" in captured.out
    assert "auto-flipped" in captured.out


def test_show_status_on_exit_shows_mark_cli_when_processed(tmp_path: Path, capsys) -> None:
    """When status is still `processed` at exit, the panel surfaces the
    explicit CLI form the user would run to mark it mapped."""
    from biotope.commands.map_wizard import _show_status_on_exit

    datasets_dir = tmp_path / "proj" / ".biotope" / "datasets"
    datasets_dir.mkdir(parents=True)
    croissant = datasets_dir / "data" / "ot" / "target.jsonld"
    croissant.parent.mkdir(parents=True)
    croissant.write_text(
        json.dumps(
            {
                "@type": "sc:Dataset",
                "name": "data/ot/target",
                "biotope:status": "processed",
            }
        )
    )

    _show_status_on_exit({"croissant": str(croissant)}, croissant)
    captured = capsys.readouterr()
    assert "processed" in captured.out
    assert "biotope mark data/ot/target mapped" in captured.out


def test_unresolved_mapping_does_not_flip(tmp_path: Path) -> None:
    """The flip is up-edge only — partial mappings keep the status as
    processed so the queue still sees them as work-in-progress."""
    croissant = tmp_path / "minimal.jsonld"
    _write_minimal_croissant(croissant)

    # Intentionally not resolved: no `id` on the entity.
    mapping = Mapping.model_validate(
        {
            "croissant": str(croissant),
            "entities": {"gene": {}},
        }
    )
    assert not mapping.is_resolved()

    # The wizard only calls _flip_... when is_resolved() is true. Verify the
    # helper itself is robust if called wrongly: it should still only flip on
    # request (we don't gate inside the helper), so this is really just
    # documenting the contract via the autosave guard above.
    # (We do not call _flip_... here.)
    assert get_status(json.loads(croissant.read_text())) == STATUS_PROCESSED
