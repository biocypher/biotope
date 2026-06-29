"""Tests for BioCypher CSV filename helpers."""

from biotope.croissant.biocypher_labels import escape_node_id, schema_term_to_csv_stem


def test_schema_term_to_csv_stem_single_word() -> None:
    assert schema_term_to_csv_stem("tool") == "Tool"


def test_schema_term_to_csv_stem_sentence_case() -> None:
    assert schema_term_to_csv_stem("node organizes event") == "NodeOrganizesEvent"


def test_schema_term_to_csv_stem_snake_key_not_used() -> None:
    """input_label snake_case must not be passed here — only schema terms."""
    assert schema_term_to_csv_stem("gene in disease") == "GeneInDisease"
    assert schema_term_to_csv_stem("gene_in_disease") == "Gene_in_disease"


def test_escape_node_id_strips_control_chars() -> None:
    assert escape_node_id("ensembl:1\n2") == "ensembl:1 2"
    assert escape_node_id("ensembl:1\r\n2") == "ensembl:1  2"
    assert escape_node_id("ensembl:1\x002") == "ensembl:1 2"


def test_escape_node_id_passes_through_quotes() -> None:
    """Quote escaping is BioCypher's CSV writer's job; we must not double-escape."""
    assert escape_node_id('ensembl:o\'brien"s') == 'ensembl:o\'brien"s'
