from pathlib import Path

from biotope.croissant.codegen.schema import render_schema_module
from biotope.croissant.spec import load_from_path


def test_render_minimal_module(minimal_croissant: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    rendered = render_schema_module(dataset)

    # The module declares the expected dataset class.
    assert "class DatasetGenes(Dataset):" in rendered
    # And one field class per scalar field.
    assert "class FieldGenesEnsemblId(ScalarField):" in rendered
    assert "class FieldGenesSymbol(ScalarField):" in rendered
    assert "class FieldGenesBiotype(ScalarField):" in rendered
    # Late attributes are emitted after the class bodies.
    assert 'DatasetGenes.id = "genes"' in rendered


def test_rendered_module_is_executable(minimal_croissant: Path, tmp_path: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    rendered = render_schema_module(dataset)
    module_path = tmp_path / "_generated_schema.py"
    module_path.write_text(rendered)

    namespace: dict[str, object] = {}
    exec(compile(rendered, str(module_path), "exec"), namespace)  # noqa: S102

    DatasetGenes = namespace["DatasetGenes"]
    assert DatasetGenes.id == "genes"
    assert len(DatasetGenes.fields) == 3
