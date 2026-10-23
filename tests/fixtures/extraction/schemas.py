from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(frozen=True)
class Profile:
    """A researcher's profile page on an institute website."""

    name: str = field(metadata={"description": "The researcher's full name, without academic titles."})
    group: str | None = field(metadata={"description": "The research group the researcher belongs to."})
    methods: list[str] = field(metadata={"description": "Each experimental or computational method the page lists."})


@dataclass(frozen=True)
class FundingRound:
    """One funding round of a call for proposals."""

    __record_key__: ClassVar[tuple[str, ...]] = ("round",)

    round: str | None = field(metadata={"description": "The round's name as the call gives it."})
    deadline: str | None = field(metadata={"description": "The round's submission deadline, as written."})
    budget: str | None = field(metadata={"description": "The maximum budget per project in the round, as written."})
