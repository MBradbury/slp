
import itertools

from simulator.Topology import Ring, Grid

from scipy.spatial.distance import euclidean

class Configuration(object):
    def __init__(self, topology, source_id, sink_id, space_behind_sink):
        self.topology = topology
        self.sink_id = int(sink_id)
        self.source_id = int(source_id)
        self.space_behind_sink = space_behind_sink

        if self.sink_id >= len(self.topology.nodes):
            raise RuntimeError("There are not enough nodes ({}) to have a sink id of {}".format(len(self.topology.nodes), self.sink_id))

        if self.source_id >= len(self.topology.nodes):
            raise RuntimeError("There are not enough nodes ({}) to have a source id of {}".format(len(self.topology.nodes), self.source_id))

        self.connectivity_matrix = None
        self.shortest_path = None

    def build_arguments(self):
        build_arguments = {
            "SOURCE_NODE_ID": self.source_id,
            "SINK_NODE_ID": self.sink_id
        }

        if self.space_behind_sink:
            build_arguments.update({"ALGORITHM": "GenericAlgorithm"})
        else:
            build_arguments.update({"ALGORITHM": "FurtherAlgorithm"})

        return build_arguments

    def __str__(self):
        return "Configuration<sink_id={}, source_id={}, space_behind_sink={}, topology={}>".format(
            self.sink_id, self.source_id, self.space_behind_sink, self.topology
        )

    def build_connectivity_matrix(self):
        if self.connectivity_matrix is None or self.shortest_path is None:
            import numpy
            from scipy.sparse import csr_matrix
            from scipy.sparse.csgraph import shortest_path

            self.connectivity_matrix = numpy.zeros((self.size(), self.size()))

            for (y, x) in itertools.product(xrange(self.size()), xrange(self.size())):
                self.connectivity_matrix[x][y] = 1 if self.is_connected(x, y) else 0
            self.connectivity_matrix = csr_matrix(self.connectivity_matrix)

            self.shortest_path = shortest_path(self.connectivity_matrix)

    def size(self):
        return len(self.topology.nodes)

    def is_connected(self, i, j):
        nodes = self.topology.nodes
        return euclidean(nodes[i], nodes[j]) <= self.topology.distance

    def one_hop_neighbours(self, node):
        for i in xrange(len(self.topology.nodes)):
            if i != node and self.is_connected(node, i):
                yield i

    def ssd(self):
        """The number of hops between the sink and the source nodes"""
        self.build_connectivity_matrix()
        return self.shortest_path[self.source_id, self.sink_id]

    def node_sink_distance(self, node):
        self.build_connectivity_matrix()
        return self.shortest_path[node, self.sink_id]

    def node_source_distance(self, node):
        self.build_connectivity_matrix()
        return self.shortest_path[node, self.source_id]


def CreateSourceCorner(network_size, distance):
    grid = Grid(network_size, distance)

    return Configuration(
        grid,
        source_id=0,
        sink_id=(len(grid.nodes) - 1) / 2,
        space_behind_sink=True
    )

def CreateSinkCorner(network_size, distance):
    grid = Grid(network_size, distance)

    return Configuration(
        grid,
        source_id=(len(grid.nodes) - 1) / 2,
        sink_id=len(grid.nodes) - 1,
        space_behind_sink=False
    )

def CreateFurtherSinkCorner(network_size, distance):
    grid = Grid(network_size, distance)

    return Configuration(
        grid,
        source_id=(network_size + 1) * 3,
        sink_id=len(grid.nodes) - 1,
        space_behind_sink=False
    )

def CreateGeneric1(network_size, distance):
    grid = Grid(network_size, distance)

    node_count = len(grid.nodes)

    return Configuration(
        grid,
        source_id=(network_size / 2) - (node_count / 3),
        sink_id=(network_size / 2) + (node_count / 3),
        space_behind_sink=False
    )

def CreateGeneric2(network_size, distance):
    grid = Grid(network_size, distance)

    return Configuration(
        grid,
        source_id=(network_size * (network_size - 2)) - 2 - 1,
        sink_id=(network_size * 2) + 2,
        space_behind_sink=True
    )


def CreateRingTop(network_size, distance):
    ring = Ring(network_size, distance)

    return Configuration(
        ring,
        source_id=network_size - 1,
        sink_id=0,
        space_behind_sink=True
    )

def CreateRingMiddle(network_size, distance):
    ring = Ring(network_size, distance)

    return Configuration(
        ring,
        source_id=(4 * network_size - 5) / 2 + 1,
        sink_id=(4 * network_size - 5) / 2,
        space_behind_sink=True
    )

def CreateRingOpposite(network_size, distance):
    ring = Ring(network_size, distance)

    return Configuration(
        ring,
        source_id=len(ring.nodes) - 1,
        sink_id=0,
        space_behind_sink=True
    )

MAPPING = {
    "SourceCorner": CreateSourceCorner,
    "SinkCorner": CreateSinkCorner,
    "FurtherSinkCorner": CreateFurtherSinkCorner,
    "Generic1": CreateGeneric1,
    "Generic2": CreateGeneric2,

    "RingTop": CreateRingTop,
    "RingMiddle": CreateRingMiddle,
    "RingOpposite": CreateRingOpposite,
}

CONFIGURATION_RANK = {
    'SourceCorner': 1,
    'SinkCorner': 2,
    'FurtherSinkCorner': 3,
    'Generic1': 4,
    'Generic2': 5,

    'CircleSinkCentre': 6,
    'CircleSourceCentre': 7,
    'CircleEdges': 8,

    'RingTop': 9,
    'RingMiddle': 10,
    'RingOpposite': 11,
}

def Names():
    return MAPPING.keys()

def Create(name, args):
    return MAPPING[name](args.network_size, args.distance)
