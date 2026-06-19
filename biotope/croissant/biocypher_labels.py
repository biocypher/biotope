"""BioCypher CSV filename helpers for biotope view.

BioCypher names Neo4j/CSV output files from schema *terms* (YAML top-level keys),
not ``input_label``. These helpers mirror BioCypher's ``parse_label`` and
``name_sentence_to_pascal`` so ``biotope view`` can classify node vs edge files.
"""

from __future__ import annotations

import re


def parse_label(label: str) -> str:
    """Strip characters Neo4j disallows from a schema term (BioCypher parity)."""
    allowed_chars = r"a-zA-Z0-9_$ ."
    matches = re.findall(f"[{allowed_chars}]", label)
    if not matches:
        return ""

    def first_character_compliant(character: str) -> bool:
        return character.isalpha() or character == "$"

    if not first_character_compliant(matches[0]):
        for index, char in enumerate(matches):
            if first_character_compliant(char):
                matches = matches[index:]
                break
    return "".join(matches).strip()


def sentencecase_to_pascalcase(s: str, sep: str = r"\s") -> str:
    """Convert sentence case to PascalCase (BioCypher ``_misc.sentencecase_to_pascalcase``)."""
    return re.sub(
        r"(?:^|[" + sep + "])([a-zA-Z])",
        lambda match: match.group(1).upper(),
        s,
    )


def name_sentence_to_pascal(name: str) -> str:
    """Convert a schema term to the CSV file stem BioCypher writes."""
    if "." in name:
        return ".".join(sentencecase_to_pascalcase(part) for part in name.split("."))
    return sentencecase_to_pascalcase(name)


def schema_term_to_csv_stem(schema_term: str) -> str:
    """Map a ``schema_config.yaml`` top-level key to its output CSV basename stem."""
    return name_sentence_to_pascal(parse_label(schema_term))


_UNSAFE_ID_CHARS = re.compile(r"[\r\n\x00]")


def escape_node_id(value: str) -> str:
    """Strip characters that break ``neo4j-admin database import`` regardless
    of CSV quoting (embedded newlines/carriage returns/NUL bytes split a row
    mid-record even inside a quoted field). Quote-character escaping is left
    to BioCypher's own CSV writer, which already handles RFC 4180 quoting —
    re-escaping here would double-escape.
    """
    return _UNSAFE_ID_CHARS.sub(" ", value)
