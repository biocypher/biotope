from biotope.graph import Topology

from .gene.node import Gene
from .paper.node import Paper
from .person.authored import Authored
from .person.node import Person


TOPOLOGY = Topology(nodes=(Gene, Person, Paper), edges=(Authored,))
