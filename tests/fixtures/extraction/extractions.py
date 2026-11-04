from biotope.extraction import Extraction

from .readers import FundingRound, Profile, ProfileReader, RoundReader


EXTRACTIONS: tuple[Extraction, ...] = (
    Extraction(name="profile", schema=Profile, extractor=ProfileReader, files=("data/**/pages/*.html",), parallel=2),
    Extraction(name="funding_round", schema=FundingRound, extractor=RoundReader, files=("data/calls/*.md",)),
)
