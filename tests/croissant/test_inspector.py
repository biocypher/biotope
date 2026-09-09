"""Inspect real-shaped metadata without opening source payloads."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

from click.testing import CliRunner
from rich.console import Console

from biotope.commands.map import map_group
from biotope.croissant import inspector
from biotope.croissant.inspector import inspect_dataset
from biotope.croissant.spec import CroissantDatasetModel


def test_long_sources_and_fields_wrap_without_repeating_baker_boilerplate() -> None:
    source = "44161_2025_626_MOESM3_ESM.xlsx - fibroblast_cohort_characteristics_formatted.csv"
    other = "44161_2025_626_MOESM3_ESM.xlsx - Marker genes for each fibroblast subtype.csv"
    long_field = "snRNAseq_cohort_characteristics_" * 3 + "[bold]"
    record_sets = []
    for index, path in enumerate((source, other)):
        record_sets.append(
            {
                "@id": f"record/{index}",
                "name": Path(path).stem,
                "description": f"Records from {path}",
                "field": [
                    {
                        "@id": f"record/{index}/disease_id",
                        "name": "disease_id",
                        "dataType": "cr:Int64",
                        "description": f"Column 'disease_id' from {path}",
                        "source": {"fileObject": {"@id": str(index)}, "extract": {"column": "disease_id"}},
                    },
                    {
                        "name": long_field,
                        "dataType": "sc:Text",
                        "description": "Keep leading zeros. [bold] is literal.",
                    },
                ],
            }
        )
    # A parse note attached to generated text is significant, even with a boilerplate prefix.
    record_sets[1]["description"] += ". Partial parse: final table still open."
    inspection = inspect_dataset(
        CroissantDatasetModel.model_validate(
            {
                "name": "raw",
                "recordSet": record_sets,
                "distribution": [
                    {"@type": "cr:FileObject", "@id": str(i), "contentUrl": path}
                    for i, path in enumerate((source, other))
                ],
            }
        )
    )
    output = StringIO()
    inspector.render_inspection(inspection, Console(file=output, width=64, color_system=None))
    text = output.getvalue()
    lines = text.splitlines()
    assert max(map(len, lines)) <= 64
    assert "…" not in text and "..." not in text
    assert "".join(source.split()) in "".join(text.split())
    assert "".join(other.split()) in "".join(text.split())
    assert long_field in "".join(text.split())
    assert "Column 'disease_id'" not in text
    assert "Records from " + source not in " ".join(text.split())
    assert "Partial parse: final table still open." in " ".join(text.split())
    assert "Keep leading zeros. [bold] is literal." in " ".join(text.split())
    assert text.count("SOURCE") == 2  # Shared filename prefixes are not a workbook relationship.
    assert "RECORD" not in text
    assert text.index("disease_id") < text.index("snRNAseq")
    field_lines = [line for line in lines if line.startswith(("Int64", "Text"))]
    assert len(field_lines) == 4
    assert field_lines[0].index("disease_id") == field_lines[1].index("snRNAseq")
    assert "identifier-like" not in text and "explode" not in text


def test_cli_json_preserves_nested_identity_sources_and_annotations(tmp_path: Path) -> None:
    workbook = "/absent/very_long_cohort,study_metadata[final].xlsx"
    manifest = {
        "@id": "dataset:study",
        "@context": {"custom": "https://example.org/types/"},
        "name": "study",
        "description": "Metadata curated from the study supplement.",
        "distribution": [
            {"@type": "cr:FileObject", "@id": "workbook", "contentUrl": workbook, "sha256": "abc"},
            {"@type": "cr:FileSet", "@id": "parts", "includes": ["part,one.parquet", "part,two.parquet"]},
        ],
        "recordSet": [
            {
                "@id": "sheet/a",
                "name": "Participants",
                "description": "One row per participant.",
                "field": [
                    {
                        "@id": "sheet/a/samples",
                        "name": "samples",
                        "description": "Column 'samples' of sheet 'Participants' in " + workbook,
                        "isArray": True,
                        "cr:arrayShape": "2,3",
                        "source": {"fileObject": {"@id": "workbook"}, "extract": {"sheet": "Participants"}},
                        "subField": [
                            {
                                "@id": "sheet/a/samples/id",
                                "name": "id",
                                "description": "Column 'id'",
                                "dataType": "sc:Text",
                                "references": {"field": {"@id": "sheet/b/id"}},
                            },
                            {"@id": "sheet/a/samples/date", "name": "date", "dataType": "sc:DateTime"},
                        ],
                    }
                ],
            },
            {
                "@id": "sheet/b",
                "name": "Visits",
                "field": [
                    {
                        "@id": "sheet/b/id",
                        "name": "id",
                        "source": {"fileObject": {"@id": "workbook"}, "extract": {"sheet": "Visits"}},
                    }
                ],
            },
            {
                "@id": "joined",
                "name": "Joined samples",
                "field": [
                    {"@id": "joined/", "source": {"fileSet": {"@id": "parts"}, "transform": [{"regex": ".*"}]}},
                    {"name": "custom", "dataType": "custom:Label", "source": {"fileObject": {"@id": "missing"}}},
                ],
            },
        ],
    }
    path = tmp_path / "study.jsonld"
    path.write_text(json.dumps(manifest))
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(map_group, ["inspect", str(path), "--json"])
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 2
    assert payload["id"] == manifest["@id"]
    assert payload["context"] == manifest["@context"]
    assert payload["distribution"] == manifest["distribution"]
    assert [r["id"] for r in payload["record_sets"]] == ["sheet/a", "sheet/b", "joined"]
    assert [r["source_ids"] for r in payload["record_sets"]] == [["workbook"], ["workbook"], ["parts", "missing"]]
    samples = payload["record_sets"][0]["fields"][0]
    assert samples["id"] == "sheet/a/samples"
    assert samples["repeated"] is True and samples["array_shape"] == "2,3"
    assert samples["source"] == manifest["recordSet"][0]["field"][0]["source"]
    assert [f["id"] for f in samples["sub_fields"]] == ["sheet/a/samples/id", "sheet/a/samples/date"]
    assert samples["sub_fields"][1]["data_type"] == "sc:DateTime"
    assert samples["sub_fields"][0]["attributes"]["references"] == {"field": {"@id": "sheet/b/id"}}
    unnamed = payload["record_sets"][2]["fields"][0]
    assert unnamed["id"] == unnamed["name"] == "joined/"
    assert unnamed["source"]["transform"] == [{"regex": ".*"}]

    human = runner.invoke(map_group, ["inspect", str(path)])
    assert human.exit_code == 0, human.output
    text = human.stdout
    assert text.count(workbook) == 1
    assert "Participants" in text and "Visits" in text
    assert "One row per participant." in text
    assert "2,3" in text and "Struct" in text and "DateTime" in text
    assert "├─ id" in text and "└─ date" in text
    assert "part,one.parquet" in text and "part,two.parquet" in text
    assert "Unresolved source: missing" in text
    assert "custom:Label" in text
    assert "Not declared" in text
    assert "Column '" not in text
