
import math, itertools

from simulator.Topology import *

from scipy.spatial.distance import euclidean

class Configuration:
    def __init__(self, topology, sourceId, sinkId, spaceBehindSink):
        self.topology = topology
        self.sinkId = int(sinkId)
        self.sourceId = int(sourceId)
        self.spaceBehindSink = spaceBehindSink

        if self.sinkId >= len(self.topology.nodes):
            raise Exception("There are not enough nodes ({}) to have a sink id of {}".format(len(self.topology.nodes), self.sinkId))

        if self.sourceId >= len(self.topology.nodes):
            raise Exception("There are not enough nodes ({}) to have a source id of {}".format(len(self.topology.nodes), self.source))

    def getBuildArguments(self):
        build_arguments = {
            "SOURCE_NODE_ID": self.sourceId,
            "SINK_NODE_ID": self.sinkId
        }

        if self.spaceBehindSink:
            build_arguments.update({"ALGORITHM": "GenericAlgorithm"})
        else:
            build_arguments.update({"ALGORITHM": "FurtherAlgorithm"})

        return build_arguments

    def __str__(self):
        return "Configuration<sinkId={}, sourceId={}, spaceBehindSink={}, topology={}>".format(
            self.sinkId, self.sourceId, self.spaceBehindSink, self.topology
            )

    def build_connectivity_matrix(self):
        if self.connectivity_matrix is None or self.sp is None:
            import numpy
            from scipy.sparse import csr_matrix
            from scipy.sparse.csgraph import shortest_path

            self.connectivity_matrix = numpy.zeros((self.size, self.size))

            for (y, x) in itertools.product(xrange(self.size), xrange(self.size)):
                self.connectivity_matrix[x][y] = 1 if self.is_connected(x, y) else 0
            self.connectivity_matrix = csr_matrix(self.connectivity_matrix)

            self.sp = shortest_path(self.connectivity_matrix)

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
        return self.sp[self.sourceId, self.sinkId]

    def node_sink_distance(self, node):
        self.build_connectivity_matrix()
        return self.sp[node, self.sinkId]

    def node_source_distance(self, node):
        self.build_connectivity_matrix()
        return self.sp[node, self.sourceId]


def CreateSourceCorner(network_size, distance):
    grid = Grid(network_size, distance)

    return Configuration(grid,
        sourceId=0,
        sinkId=(len(grid.nodes) - 1) / 2,
        spaceBehindSink=True)

def CreateSinkCorner(network_size, distance):
    grid = Grid(network_size, distance)

    return Configuration(grid,
        sourceId=(len(grid.nodes) - 1) / 2,
        sinkId=len(grid.nodes) - 1,
        spaceBehindSink=False)

def CreateFurtherSinkCorner(network_size, distance):
    grid = Grid(network_size, distance)

    return Configuration(grid,
        sourceId=(network_size + 1) * 3,
        sinkId=len(grid.nodes) - 1,
        spaceBehindSink=False)

def CreateGeneric1(network_size, distance):
    grid = Grid(network_size, distance)

    node_count = len(grid.nodes)

    return Configuration(grid,
        sourceId=(network_size / 2) - (node_count / 3),
        sinkId=(network_size / 2) + (node_count / 3),
        spaceBehindSink=False)

def CreateGeneric2(network_size, distance):
    grid = Grid(network_size, distance)

    return Configuration(grid,
        sourceId=(network_size * (network_size - 2)) - 2 - 1,
        sinkId=(network_size * 2) + 2,
        spaceBehindSink=True)


def CreateRingTop(network_size, distance):
    ring = Ring(network_size, distance)

    return Configuration(ring,
        sourceId=network_size - 1,
        sinkId=0,
        spaceBehindSink=True)

def CreateRingMiddle(network_size, distance):
    ring = Ring(network_size, distance)

    return Configuration(ring,
        sourceId=(4 * network_size - 5) / 2 + 1,
        sinkId=(4 * network_size - 5) / 2,
        spaceBehindSink=True)

def CreateRingOpposite(network_size, distance):
    ring = Ring(network_size, distance)

    return Configuration(ring,
        sourceId=len(ring.nodes) - 1,
        sinkId=0,
        spaceBehindSink=True)

configurationMapping = {
    "SourceCorner": CreateSourceCorner,
    "SinkCorner": CreateSinkCorner,
    "FurtherSinkCorner": CreateFurtherSinkCorner,
    "Generic1": CreateGeneric1,
    "Generic2": CreateGeneric2,

    "RingTop": CreateRingTop,
    "RingMiddle": CreateRingMiddle,
    "RingOpposite": CreateRingOpposite,
}

configurationRank = {
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
    return configurationMapping.keys()

def Create(name, args):
    return configurationMapping[name](args.network_size, args.distance)
