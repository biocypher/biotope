"""Register generated source contracts; keep each authored loader beside its schema."""

from biotope.graph import SourceContract


# Generation writes one package per record set, plus a CONTRACTS inventory per
# manifest. Selecting from it stays a project decision:
#
#     from .raw import CONTRACTS               # every record set of raw.jsonld
#     from .raw.measurements import SOURCE as MEASUREMENTS
#
#     SOURCES: tuple[SourceContract, ...] = (MEASUREMENTS,)
#
# A decoding helper shared by several loaders is authored code and may live
# anywhere under graph/, including beside the packages it serves; only
# directories holding a generated schema.py are treated as source packages.
SOURCES: tuple[SourceContract, ...] = ()
