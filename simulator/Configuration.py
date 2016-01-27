
import itertools

from simulator.Topology import SimpleTree, Line, Ring, Grid, Random

from scipy.spatial.distance import euclidean

from data.memoize import memoize

class Configuration(object):
    def __init__(self, topology, source_ids, sink_id, space_behind_sink):
        self.topology = topology
        self.sink_id = int(sink_id)
        self.source_ids = {int(source_id) for source_id in source_ids}
        self.space_behind_sink = space_behind_sink

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

    def build_connectivity_matrix(self, return_predecessors=False):
        if self._dist_matrix is None or (self._predecessors is None and return_predecessors):
            import numpy
            from scipy.sparse import csr_matrix
            from scipy.sparse.csgraph import shortest_path

            connectivity_matrix = numpy.zeros((self.size(), self.size()))

            for (y, x) in itertools.product(xrange(self.size()), xrange(self.size())):
                connectivity_matrix[x][y] = 1 if self.is_connected(x, y) else 0
            connectivity_matrix = csr_matrix(connectivity_matrix)

            ret = shortest_path(connectivity_matrix, return_predecessors=return_predecessors)

            if return_predecessors:
                self._dist_matrix, self._predecessors = ret
            else:
                self._dist_matrix = ret

    def size(self):
        return len(self.topology.nodes)

    def is_connected(self, i, j):
        nodes = self.topology.nodes
        return euclidean(nodes[i], nodes[j]) <= self.topology.distance

    def one_hop_neighbours(self, node):
        for i in xrange(len(self.topology.nodes)):
            if i != node and self.is_connected(node, i):
                yield i

    def ssd(self, source_id):
        """The number of hops between the sink and the source nodes"""
        if source_id not in self.source_ids:
            raise RuntimeError("Invalid source")

        return self.node_sink_distance(source_id)

    def node_sink_distance(self, node):
        self.build_connectivity_matrix()
        return self._dist_matrix[node, self.sink_id]

    def node_source_distance(self, node, source_id):
        if source_id not in self.source_ids:
            raise RuntimeError("Invalid source")

        self.build_connectivity_matrix()
        return self._dist_matrix[node, source_id]

    def shortest_path(self, node_from, node_to):
        self.build_connectivity_matrix(return_predecessors=True)

        path = []

        node = node_to
        while node != node_from:
            path.append(node)
            node = self._predecessors[node_from, node]

        path.append(node)

        return path[::-1]


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

class SinkCorner(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(SinkCorner, self).__init__(
            grid,
            source_ids={(len(grid.nodes) - 1) / 2},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=False
        )

class FurtherSinkCorner(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(FurtherSinkCorner, self).__init__(
            grid,
            source_ids={(network_size + 1) * 3},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=False
        )

class Generic1(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)
        node_count = len(grid.nodes)

        super(Generic1, self).__init__(
            grid,
            source_ids={(network_size / 2) - (node_count / 3)},
            sink_id=(network_size / 2) + (node_count / 3),
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

class Source4Corners(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(Source4Corners, self).__init__(
            grid,
            source_ids={0, network_size - 1, len(grid.nodes) - network_size, len(grid.nodes) - 1},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
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

class Source3Corner(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(Source3Corner, self).__init__(
            grid,
            source_ids={0, 3, network_size * 3},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

# TODO: rename Source2Corner2OppositeCorner
class Source4Corner(Configuration):
    def __init__(self, network_size, distance):
        grid = Grid(network_size, distance)

        super(Source4Corner, self).__init__(
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
    def __init__(self, network_size, distance):
        random = Random(network_size, distance)

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
    return [cls for cls in configurations() if cls.__name__ == name][0](network_size, distance)

def create(name, args):
    return create_specific(name, args.network_size, args.distance)
