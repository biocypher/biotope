import csv
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THRESHOLD = 0.8
HEADER = """# curie_map:
#   directory: https://example.org/directory/
#   roster: https://example.org/roster/
#   semapv: https://w3id.org/semapv/vocab/
#   skos: http://www.w3.org/2004/02/skos/core#
# mapping_set_id: https://example.org/identity-fixture/similar-names
# license: https://creativecommons.org/publicdomain/zero/1.0/
"""


def rows(name: str) -> list[dict[str, str]]:
    with (ROOT / "raw" / name).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def main() -> None:
    links = []
    for person in rows("roster.csv"):
        for account in rows("directory.csv"):
            score = SequenceMatcher(None, person["name"].lower(), account["name"].lower()).ratio()
            if score >= THRESHOLD:
                links.append((f"roster:{person['record']}", f"directory:{account['upn']}", f"{score:.3f}"))
    with (ROOT / "raw/matches.sssom.tsv").open("w", newline="", encoding="utf-8") as stream:
        stream.write(HEADER)
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(["subject_id", "predicate_id", "object_id", "mapping_justification", "confidence"])
        for subject, target, score in sorted(links):
            writer.writerow([subject, "skos:exactMatch", target, "semapv:LexicalMatching", score])


if __name__ == "__main__":
    main()
