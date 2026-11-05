"""Register typed transformation functions, one module per group of mappings, such as mappings/person.py."""

from biotope.graph import MappingEntry

from .airline import AIRLINES
from .airport import AIRPORTS
from .role import ROLES


MAPPINGS: tuple[MappingEntry, ...] = (AIRPORTS, AIRLINES, ROLES)
