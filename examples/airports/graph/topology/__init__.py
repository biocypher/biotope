"""Register each node from topology/<node>/node.py and each edge from topology/<source node>/<edge>.py."""

from biotope.graph import Topology

from .airline.airline_role_at_airport import AirlineRoleAtAirport
from .airline.node import Airline
from .airport.node import Airport


TOPOLOGY = Topology(nodes=(Airport, Airline), edges=(AirlineRoleAtAirport,))
