from __future__ import print_function, division

import numpy as np
from scipy.sparse.csgraph import shortest_path
from scipy.spatial.distance import cdist

from data.memoize import memoize
from simulator.Topology import SimpleTree, Line, Ring, Grid, Random

class Configuration(object):
    def __init__(self, topology, source_ids, sink_id, space_behind_sink):
        self.topology = topology
        self.sink_id = int(sink_id)
        self.source_ids = {int(source_id) for source_id in source_ids}
        self.space_behind_sink = space_behind_sink

        if self.sink_id < 0:
            raise RuntimeError("The sink id must be positive")

        if any(source_id < 0 for source_id in self.source_ids):
            raise RuntimeError("All source ids must be positive")

        if self.sink_id >= len(self.topology.nodes):
            raise RuntimeError(
                "There are not enough nodes ({}) to have a sink id of {}".format(
                    len(self.topology.nodes), self.sink_id))

        if any(source_id >= len(self.topology.nodes) for source_id in self.source_ids):
            raise RuntimeError(
                "There are not enough nodes ({}) to have a source id of {}".format(
                    len(self.topology.nodes), self.source_ids))

        self._dist_matrix = None
        self._predecessors = None

        self._build_connectivity_matrix()

    def build_arguments(self):
        build_arguments = {
            "SINK_NODE_ID": self.sink_id
        }

        if self.space_behind_sink:
            build_arguments["ALGORITHM"] = "GenericAlgorithm"
            build_arguments["SPACE_BEHIND_SINK"] = "1"
        else:
            build_arguments["ALGORITHM"] = "FurtherAlgorithm"
            build_arguments["NO_SPACE_BEHIND_SINK"] = "1"

        return build_arguments

    def __str__(self):
        return "Configuration<sink_id={}, source_ids={}, space_behind_sink={}, topology={}>".format(
            self.sink_id, self.source_ids, self.space_behind_sink, self.topology
        )

    def _build_connectivity_matrix(self):
        self._dist_matrix_meters = cdist(self.topology.nodes, self.topology.nodes, 'euclidean')

        connectivity_matrix = self._dist_matrix_meters <= self.topology.distance

        self._dist_matrix, self._predecessors = shortest_path(connectivity_matrix, directed=True, return_predecessors=True)

    def size(self):
        return len(self.topology.nodes)

    def is_connected(self, i, j):
        return self._dist_matrix_meters[i,j] <= self.topology.distance

    def one_hop_neighbours(self, node):
        for i in range(len(self.topology.nodes)):
            if i != node and self.is_connected(node, i):
                yield i

    def node_distance(self, node1, node2):
        return self._dist_matrix[node1, node2]

    def ssd(self, source_id):
        """The number of hops between the sink and the specified source node"""
        if source_id not in self.source_ids:
            raise RuntimeError("Invalid source ({} not in {})".format(source_id, self.source_ids))

        return self.node_sink_distance(source_id)

    def node_sink_distance(self, node):
        """The number of hops between the sink and the specified node"""
        return self._dist_matrix[node, self.sink_id]

    def node_source_distance(self, node, source_id):
        """The number of hops between the specified source and the specified node"""
        if source_id not in self.source_ids:
            raise RuntimeError("Invalid source ({} not in {})".format(source_id, self.source_ids))

        return self._dist_matrix[node, source_id]

    def node_distance_meters(self, node1, node2):
        return self._dist_matrix_meters[node1,node2]

    def ssd_meters(self, source_id):
        """The number of meters between the sink and the specified source node"""
        if source_id not in self.source_ids:
            raise RuntimeError("Invalid source ({} not in {})".format(source_id, self.source_ids))

        return self.node_sink_distance_meters(source_id)

    def node_sink_distance_meters(self, node):
        """The number of meters between the sink and the specified node"""
        return self.topology.node_distance_meters(self.sink_id, node)

    def node_source_distance_meters(self, node, source_id):
        """The number of meters between the specified source and the specified node"""
        if source_id not in self.source_ids:
            raise RuntimeError("Invalid source ({} not in {})".format(source_id, self.source_ids))

        return self.topology.node_distance_meters(node, source_id)



    def shortest_path(self, node_from, node_to):
        """Returns a list of nodes that will take you from node_from to node_to along the shortest path."""

        path = []

        node = node_to
        while node != node_from:
            path.append(node)
            node = self._predecessors[node_from, node]

        path.append(node)

        return path[::-1]


    def minxy_coordinates(self):
        """Finds the minimum x and y coordinates. A node may not be present at these coordinates."""
        nodes = self.topology.nodes

        minx = min(x for (x, y) in nodes)
        miny = min(y for (x, y) in nodes)

        return (minx, miny)

    def maxxy_coordinates(self):
        """Finds the maximum x and y coordinates. A node may not be present at these coordinates."""
        nodes = self.topology.nodes

        maxx = max(x for (x, y) in nodes)
        maxy = max(y for (x, y) in nodes)

        return (maxx, maxy)


class LineSinkCentre(Configuration):
    def __init__(self, network_size, distance):
        line = Line(network_size, distance)

        super(LineSinkCentre, self).__init__(
            line,
            source_ids={0},
            sink_id=(len(line.nodes) - 1) / 2,
            space_behind_sink=True
        )

class SimpleTreeSinkEnd(Configuration):
    def __init__(self, network_size, distance):
        tree = SimpleTree(network_size, distance)

        super(SimpleTreeSinkEnd, self).__init__(
            tree,
            source_ids={0},
            sink_id=network_size - 1,
            space_behind_sink=True
        )

class SourceCorner(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(SourceCorner, self).__init__(
            grid,
            source_ids={0},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class Source2CornerTop(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(Source2CornerTop, self).__init__(
            grid,
            source_ids={0, 2},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class Source3CornerTop(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(Source3CornerTop, self).__init__(
            grid,
            source_ids={0, 2, network_size+1},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class SinkCorner(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(SinkCorner, self).__init__(
            grid,
            source_ids={(len(grid.nodes) - 1) / 2},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=False
        )

class SinkCorner2Source(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(SinkCorner2Source, self).__init__(
            grid,
            source_ids={(len(grid.nodes) - 1)/2 - 1,(len(grid.nodes) - 1)/2 + 1},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=False
        )

class SinkCorner3Source(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(SinkCorner3Source, self).__init__(
            grid,
            source_ids={(len(grid.nodes) - 1)/2 - 1,(len(grid.nodes) - 1)/2 + 1, (len(grid.nodes) - 1) / 2 + network_size},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=False
        )

class FurtherSinkCorner(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(FurtherSinkCorner, self).__init__(
            grid,
            source_ids={0},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=False
        )
class FurtherSinkCorner2Source(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(FurtherSinkCorner2Source, self).__init__(
            grid,
            source_ids={0, 2},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=False
        )
class FurtherSinkCorner3Source(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(FurtherSinkCorner3Source, self).__init__(
            grid,
            source_ids={0, 2, network_size+1},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=False
        )

class Generic1(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)
        node_count = len(grid.nodes)

        super(Generic1, self).__init__(
            grid,
            source_ids={(node_count / 2) - (network_size / 3)},
            sink_id=(node_count / 2) + (network_size / 3),
            space_behind_sink=False
        )

class Generic2(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(Generic2, self).__init__(
            grid,
            source_ids={(network_size * (network_size - 2)) - 2 - 1},
            sink_id=(network_size * 2) + 2,
            space_behind_sink=True
        )


class RingTop(Configuration):
    def __init__(self, network_size, distance):
        ring = Ring(network_size, distance)

        super(RingTop, self).__init__(
            ring,
            source_ids={network_size - 1},
            sink_id=0,
            space_behind_sink=True
        )

class RingMiddle(Configuration):
    def __init__(self, network_size, distance):
        ring = Ring(network_size, distance)

        super(RingMiddle, self).__init__(
            ring,
            source_ids={(4 * network_size - 5) / 2 + 1},
            sink_id=(4 * network_size - 5) / 2,
            space_behind_sink=True
        )

class RingOpposite(Configuration):
    def __init__(self, network_size, distance):
        ring = Ring(network_size, distance)

        super(RingOpposite, self).__init__(
            ring,
            source_ids={len(ring.nodes) - 1},
            sink_id=0,
            space_behind_sink=True
        )


class Source2Corners(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(Source2Corners, self).__init__(
            grid,
            source_ids={0, len(grid.nodes) - 1},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class Source3Corners(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(Source3Corners, self).__init__(
            grid,
            source_ids={network_size - 1, len(grid.nodes) - network_size, len(grid.nodes) - 1},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=False
        )

class Source4Corners(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(Source4Corners, self).__init__(
            grid,
            source_ids={0, network_size - 1, len(grid.nodes) - network_size, len(grid.nodes) - 1},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=False
        )

class Source2Edges(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(Source2Edges, self).__init__(
            grid,
            source_ids={
                (network_size - 1) / 2,
                len(grid.nodes) - ((network_size - 1) / 2) - 1
            },
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class Source4Edges(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(Source4Edges, self).__init__(
            grid,
            source_ids={
                (network_size - 1) / 2,

                ((len(grid.nodes) - 1) / 2) - (network_size - 1) / 2,
                ((len(grid.nodes) - 1) / 2) + (network_size - 1) / 2,

                len(grid.nodes) - ((network_size - 1) / 2) - 1
            },
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class Source2Corner(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(Source2Corner, self).__init__(
            grid,
            source_ids={3, network_size * 3},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class FurtherSinkSource2Corner(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(FurtherSinkSource2Corner, self).__init__(
            grid,
            source_ids={3, network_size * 3},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=True
        )

class Source3Corner(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(Source3Corner, self).__init__(
            grid,
            source_ids={0, 3, network_size * 3},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class Source2Corner2OppositeCorner(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(Source2Corner2OppositeCorner, self).__init__(
            grid,
            source_ids={
                3,
                network_size * 3,
                len(grid.nodes) - (network_size * 3) - 1,
                len(grid.nodes) - 4,
            },
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class SourceEdgeCorner(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(SourceEdgeCorner, self).__init__(
            grid,
            source_ids={
                ((len(grid.nodes) - 1) / 2) + (network_size - 1) / 2,
                len(grid.nodes) - 1
            },
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class RandomConnected(Configuration):
    def __init__(self, network_size, distance, seed):
        random = Random(network_size, distance, seed=seed)

        super(RandomConnected, self).__init__(
            random,
            source_ids={len(random.nodes) - 1},
            sink_id=0,
            space_behind_sink=True
        )

def configurations():
    """A list of the available configuration classes."""
    return [cls for cls in Configuration.__subclasses__()]

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

def configuration_rank(configuration):
    return CONFIGURATION_RANK[configuration] if configuration in CONFIGURATION_RANK else len(CONFIGURATION_RANK) + 1

def names():
    return [cls.__name__ for cls in configurations()]

# Memoize this call to eliminate the overhead of creating many identical configurations.
@memoize
def create_specific(name, network_size, distance):
    confs = [cls for cls in configurations() if cls.__name__ == name]

    if len(confs) == 0:
        raise RuntimeError("No configurations were found using the name {}, size {} and distance {}".format(name, network_size, distance))

    if len(confs) > 1:
        raise RuntimeError("There are multiple configurations that have the name {}, not sure which one to choose".format(name))

    return confs[0](network_size, distance)

def create(name, args):
    return create_specific(name, args.network_size, args.distance)
