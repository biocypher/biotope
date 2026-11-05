import os
import re
from dataclasses import dataclass, field
from typing import Any, ClassVar

from biotope.extraction import Document, ExtractionError, Extractor, Schema


@dataclass(frozen=True, kw_only=True)
class Profile:
    """A researcher's profile page on an institute website."""

    name: str = field(metadata={"description": "The researcher's full name, without academic titles."})
    group: str | None = field(metadata={"description": "The research group the researcher belongs to."})
    methods: list[str] = field(metadata={"description": "Each experimental or computational method the page lists."})


@dataclass(frozen=True, kw_only=True)
class FundingRound:
    """One funding round of a call for proposals."""

    __record_key__: ClassVar[tuple[str, ...]] = ("round",)

    round: str | None = field(metadata={"description": "The round's name as the call gives it."})
    deadline: str | None = field(metadata={"description": "The round's submission deadline, as written."})
    budget: str | None = field(metadata={"description": "The maximum budget per project in the round, as written."})


class ProfileReader(Extractor):
    name = "profile-reader"
    version = "1"
    settings = {"heading": "h1"}

    def __init__(self) -> None:
        if not os.environ.get("PROFILE_READER_KEY"):
            raise ExtractionError("Set PROFILE_READER_KEY")

    def extract(self, document: Document, schema: Schema) -> list[dict[str, Any]]:
        page = document.path.read_text(encoding="utf-8")
        if "<!-- fail -->" in page:
            raise ExtractionError("the page is marked to fail")
        heading = re.search(r"<h1>(.*?)</h1>", page)
        if heading is None:
            return []
        group = re.search(r"<strong>(.*?)</strong>", page)
        return [
            {
                "name": {"value": heading[1].removeprefix("Dr. "), "quote": heading[1]},
                "group": {"value": group[1], "locator": "the first strong text"} if group else {"value": None},
                "methods": [{"value": item, "quote": item} for item in re.findall(r"<li>(.*?)</li>", page)],
            }
        ]


class RoundReader(Extractor):
    name = "round-reader"
    version = "1"

    def extract(self, document: Document, schema: Schema) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for line in document.path.read_text(encoding="utf-8").splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) != 3 or cells[0] == "Round" or not cells[0].strip("-:"):
                continue
            budget = None if cells[2] == "no funding" else cells[2]
            records.append(
                {
                    "round": {"value": cells[0], "quote": line},
                    "deadline": {"value": cells[1], "quote": line},
                    "budget": {"value": budget, "quote": line},
                }
            )
        return records
