from __future__ import print_function, division

from scipy.sparse.csgraph import shortest_path
from scipy.spatial.distance import cdist

from data.memoize import memoize
from simulator.Topology import Line, Grid, Circle, Random, SimpleTree, Ring

class Configuration(object):
    def __init__(self, topology, source_ids, sink_id, space_behind_sink):
        self.topology = topology
        self.sink_id = topology.to_ordered_nid(sink_id)
        self.source_ids = {topology.to_ordered_nid(source_id) for source_id in source_ids}
        self.space_behind_sink = space_behind_sink

        if self.sink_id < 0:
            raise RuntimeError("The sink id must be positive")

        if any(source_id < 0 for source_id in self.source_ids):
            raise RuntimeError("All source ids must be positive")

        if self.sink_id not in topology.nodes:
            raise RuntimeError(
                "The sink id {} is not present in the available node ids {}".format(
                    self.sink_id, topology.nodes))

        if any(source_id not in topology.nodes for source_id in self.source_ids):
            raise RuntimeError(
                "The a source id {} is not present in the available node ids {}".format(
                    self.source_ids, topology.nodes))

        self._dist_matrix = None
        self._predecessors = None

        self._build_connectivity_matrix()

    def build_arguments(self):
        build_arguments = {
            "SINK_NODE_ID": self.topology.to_topo_nid(self.sink_id),
            "MAX_TOSSIM_NODES": self.size(),
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
        # If there is not a uniform distance between nodes,
        # then we cannot build the connectivity matrix this way
        if not hasattr(self.topology, "distance"):
            return

        coords = list(self.topology.nodes.values())

        self._dist_matrix_meters = cdist(coords, coords, 'euclidean')

        connectivity_matrix = self._dist_matrix_meters <= self.topology.distance

        self._dist_matrix, self._predecessors = shortest_path(connectivity_matrix, directed=True, return_predecessors=True)

    def size(self):
        """The number of nodes in this configuration's topology."""
        return len(self.topology.nodes)

    def is_connected(self, ordered_nidi, ordered_nidj):
        """Check if the two ordered node ids are connected according to the wireless range."""
        if not hasattr(self.topology, "distance"):
            raise RuntimeError("Cannot know connectivity as topology does not have distance")

        return self.node_distance_meters(ordered_nidi, ordered_nidj) <= self.topology.distance

    def one_hop_neighbours(self, ordered_nid):
        """Get the one hop neighbours (within the wireless range) of the ordered node id."""
        for nid in self.topology.nodes.keys():
            if nid != ordered_nid and self.is_connected(ordered_nid, nid):
                yield nid

    def node_distance(self, ordered_nidi, ordered_nidj):
        """Get the distance between two ordered nodes in hops."""
        oi = self.topology.ordered_index

        i = oi(ordered_nidi)
        j = oi(ordered_nidj)

        return self._dist_matrix[i,j]

    def ssd(self, source_id):
        """The number of hops between the sink and the specified source node"""
        if source_id not in self.source_ids:
            raise RuntimeError("Invalid source ({} not in {})".format(source_id, self.source_ids))

        return self.node_sink_distance(source_id)

    def node_sink_distance(self, ordered_nid):
        """The number of hops between the sink and the specified node"""
        return self.node_distance(ordered_nid, self.sink_id)

    def node_source_distance(self, ordered_nid, source_id):
        """The number of hops between the specified source and the specified node"""
        if source_id not in self.source_ids:
            raise RuntimeError("Invalid source ({} not in {})".format(source_id, self.source_ids))

        return self.node_distance(ordered_nid, source_id)

    def node_distance_meters(self, ordered_nidi, ordered_nidj):
        """Get the distance between two ordered nodes in meters."""
        oi = self.topology.ordered_index

        i = oi(ordered_nidi)
        j = oi(ordered_nidj)

        return self._dist_matrix_meters[i,j]

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

        from_idx = self.topology.ordered_index(node_from)
        to_idx = self.topology.ordered_index(node_to)

        path = []

        # Start at the end
        node_idx = to_idx

        while node_idx != from_idx:
            # Add current node to path
            node = self.topology.index_to_ordered(node_idx)
            path.append(node)

            # Get next in path
            node_idx = self._predecessors[from_idx, node_idx]

        # Add final node to path
        node = self.topology.index_to_ordered(node_idx)
        path.append(node)

        # Reverse the path
        return path[::-1]


    def minxy_coordinates(self):
        """Finds the minimum x and y coordinates. A node may not be present at these coordinates."""
        nodes = self.topology.nodes.values()

        minx = min(x for (x, y) in nodes)
        miny = min(y for (x, y) in nodes)

        return (minx, miny)

    def maxxy_coordinates(self):
        """Finds the maximum x and y coordinates. A node may not be present at these coordinates."""
        nodes = self.topology.nodes.values()

        maxx = max(x for (x, y) in nodes)
        maxy = max(y for (x, y) in nodes)

        return (maxx, maxy)

    def get_node_id(self, topo_node_id_str):
        """Gets the topology node id from a node id string.
        This value could either be the topology node id as an integer,
        or it could be an attribute of the topology or configuration (e.g., 'sink_id')."""
        try:
            topo_node_id = int(topo_node_id_str)

            ord_node_id = self.topology.to_ordered_nid(topo_node_id)

            if ord_node_id not in self.topology.nodes:
                raise RuntimeError("The node id {} is not a valid node id".format(topo_node_id))

            return topo_node_id

        except ValueError:
            attr_sources = (self, self.topology)
            for attr_source in attr_sources:
                if hasattr(attr_source, topo_node_id_str):
                    ord_node_id = int(getattr(attr_source, topo_node_id_str))

                    return self.topology.to_topo_nid(ord_node_id)

            raise RuntimeError("No way to work out node from {}.".format(topo_node_id_str))

# Coordinates are specified in topology format below

class LineSinkCentre(Configuration):
    def __init__(self, *args):
        line = Line(*args)

        super(LineSinkCentre, self).__init__(
            line,
            source_ids={0},
            sink_id=(len(line.nodes) - 1) / 2,
            space_behind_sink=True
        )

class SimpleTreeSinkEnd(Configuration):
    def __init__(self, *args):
        tree = SimpleTree(*args)

        super(SimpleTreeSinkEnd, self).__init__(
            tree,
            source_ids={0},
            sink_id=tree.size - 1,
            space_behind_sink=True
        )

class SourceCorner(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(SourceCorner, self).__init__(
            grid,
            source_ids={0},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class Source2CornerTop(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(Source2CornerTop, self).__init__(
            grid,
            source_ids={0, 2},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class Source3CornerTop(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(Source3CornerTop, self).__init__(
            grid,
            source_ids={0, 2, grid.size+1},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class SinkCorner(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(SinkCorner, self).__init__(
            grid,
            source_ids={(len(grid.nodes) - 1) / 2},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=False
        )

class SinkCorner2Source(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(SinkCorner2Source, self).__init__(
            grid,
            source_ids={(len(grid.nodes) - 1)/2 - 1,(len(grid.nodes) - 1)/2 + 1},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=False
        )

class SinkCorner3Source(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(SinkCorner3Source, self).__init__(
            grid,
            source_ids={(len(grid.nodes) - 1)/2 - 1,(len(grid.nodes) - 1)/2 + 1, (len(grid.nodes) - 1) / 2 + grid.size},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=False
        )

class FurtherSinkCorner(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(FurtherSinkCorner, self).__init__(
            grid,
            source_ids={0},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=False
        )
class FurtherSinkCorner2Source(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(FurtherSinkCorner2Source, self).__init__(
            grid,
            source_ids={0, 2},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=False
        )
class FurtherSinkCorner3Source(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(FurtherSinkCorner3Source, self).__init__(
            grid,
            source_ids={0, 2, grid.size+1},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=False
        )

class SinkSourceOpposite(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(SinkSourceOpposite, self).__init__(
            grid,
            source_ids={(grid.size * 2) + 2},
            sink_id=(grid.size * (grid.size - 2)) - 2 - 1,
            space_behind_sink=True
        )

class SinkSourceOpposite2Source(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(SinkSourceOpposite2Source, self).__init__(
            grid,
            source_ids={(grid.size * 2) + 2, (grid.size * 2) + 4},
            sink_id=(grid.size * (grid.size - 2)) - 2 - 1,
            space_behind_sink=True
        )

class SinkSourceOpposite3Source(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(SinkSourceOpposite3Source, self).__init__(
            grid,
            source_ids={(grid.size * 2) + 2, (grid.size * 2) + 4, (grid.size * 2) + grid.size + 3},
            sink_id=(grid.size * (grid.size - 2)) - 2 - 1,
            space_behind_sink=True
        )

class Generic1(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)
        node_count = len(grid.nodes)

        super(Generic1, self).__init__(
            grid,
            source_ids={(node_count / 2) - (grid.size / 3)},
            sink_id=(node_count / 2) + (grid.size / 3),
            space_behind_sink=False
        )

class Generic2(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(Generic2, self).__init__(
            grid,
            source_ids={(grid.size * (grid.size - 2)) - 2 - 1},
            sink_id=(grid.size * 2) + 2,
            space_behind_sink=True
        )

class RingTop(Configuration):
    def __init__(self, *args):
        ring = Ring(*args)

        super(RingTop, self).__init__(
            ring,
            source_ids={ring.diameter - 1},
            sink_id=0,
            space_behind_sink=True
        )

class RingMiddle(Configuration):
    def __init__(self, *args):
        ring = Ring(*args)

        super(RingMiddle, self).__init__(
            ring,
            source_ids={(4 * ring.diameter - 5) / 2 + 1},
            sink_id=(4 * ring.diameter - 5) / 2,
            space_behind_sink=True
        )

class RingOpposite(Configuration):
    def __init__(self, *args):
        ring = Ring(*args)

        super(RingOpposite, self).__init__(
            ring,
            source_ids={len(ring.nodes) - 1},
            sink_id=0,
            space_behind_sink=True
        )

class CircleSinkCentre(Configuration):
    def __init__(self, *args):
        circle = Circle(*args)

        super(CircleSinkCentre, self).__init__(
            circle,
            source_ids={5},
            sink_id=circle.ordered_nid_to_topology_nid[circle.centre_node],
            space_behind_sink=True
        )

class CircleSourceCentre(Configuration):
    def __init__(self, *args):
        circle = Circle(*args)

        super(CircleSourceCentre, self).__init__(
            circle,
            source_ids={circle.ordered_nid_to_topology_nid[circle.centre_node]},
            sink_id=5,
            space_behind_sink=False
        )

class CircleEdges(Configuration):
    def __init__(self, *args):
        circle = Circle(*args)

        super(CircleEdges, self).__init__(
            circle,
            source_ids={len(circle.nodes) - 5 - 1},
            sink_id=5,
            space_behind_sink=False
        )

class Source2Corners(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(Source2Corners, self).__init__(
            grid,
            source_ids={0, len(grid.nodes) - 1},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class Source3Corners(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(Source3Corners, self).__init__(
            grid,
            source_ids={grid.size - 1, len(grid.nodes) - grid.size, len(grid.nodes) - 1},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=False
        )

class Source4Corners(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(Source4Corners, self).__init__(
            grid,
            source_ids={0, grid.size - 1, len(grid.nodes) - grid.size, len(grid.nodes) - 1},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=False
        )

class Source2Edges(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(Source2Edges, self).__init__(
            grid,
            source_ids={
                (grid.size - 1) / 2,
                len(grid.nodes) - ((grid.size - 1) / 2) - 1
            },
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class Source4Edges(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(Source4Edges, self).__init__(
            grid,
            source_ids={
                (grid.size - 1) / 2,

                ((len(grid.nodes) - 1) / 2) - (grid.size - 1) / 2,
                ((len(grid.nodes) - 1) / 2) + (grid.size - 1) / 2,

                len(grid.nodes) - ((grid.size - 1) / 2) - 1
            },
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class Source2Corner(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(Source2Corner, self).__init__(
            grid,
            source_ids={3, grid.size * 3},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class FurtherSinkSource2Corner(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(FurtherSinkSource2Corner, self).__init__(
            grid,
            source_ids={3, grid.size * 3},
            sink_id=len(grid.nodes) - 1,
            space_behind_sink=True
        )

class Source3Corner(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(Source3Corner, self).__init__(
            grid,
            source_ids={0, 3, grid.size * 3},
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class Source2Corner2OppositeCorner(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(Source2Corner2OppositeCorner, self).__init__(
            grid,
            source_ids={
                3,
                grid.size * 3,
                len(grid.nodes) - (grid.size * 3) - 1,
                len(grid.nodes) - 4,
            },
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class SourceEdgeCorner(Configuration):
    def __init__(self, *args):
        grid = Grid(*args)

        super(SourceEdgeCorner, self).__init__(
            grid,
            source_ids={
                ((len(grid.nodes) - 1) / 2) + (grid.size - 1) / 2,
                len(grid.nodes) - 1
            },
            sink_id=(len(grid.nodes) - 1) / 2,
            space_behind_sink=True
        )

class RandomConnected(Configuration):
    def __init__(self, *args):
        random = Random(*args)

        super(RandomConnected, self).__init__(
            random,
            source_ids={len(random.nodes) - 1},
            sink_id=0,
            space_behind_sink=True
        )

class DCSWarwickSrc201Sink208(Configuration):
    def __init__(self, *args, **kwargs):
        from data.testbed.dcswarwick import DCSWarwick
        dcs_warwick = DCSWarwick()

        super(DCSWarwickSrc201Sink208, self).__init__(
            dcs_warwick,
            source_ids={1},
            sink_id=2,
            space_behind_sink=True
        )

class IndriyaOneFloorSrc31Sink15(Configuration):
    def __init__(self, *args, **kwargs):
        from data.testbed.indriya import Indriya
        indriya = Indriya()

        super(IndriyaOneFloorSrc31Sink15, self).__init__(
            indriya,
            source_ids={31},
            sink_id=15,
            space_behind_sink=True
        )

class IndriyaTwoFloorsSrc31Sink60(Configuration):
    def __init__(self, *args, **kwargs):
        from data.testbed.indriya import Indriya
        indriya = Indriya()

        super(IndriyaTwoFloorsSrc31Sink60, self).__init__(
            indriya,
            source_ids={31},
            sink_id=60,
            space_behind_sink=True
        )

class EuratechSmall5by10Top(Configuration):
    def __init__(self, *args, **kwargs):
        from data.testbed.fitiotlab import Euratech
        euratech = Euratech(subset=[(96, 145)])

        super(EuratechSmall5by10Top, self).__init__(
            euratech,
            source_ids={96},
            sink_id=123,
            space_behind_sink=False
        )

class EuratechAll(Configuration):
    """A source at one end of a rectangular strip and a sink in the middle."""
    def __init__(self, *args, **kwargs):
        from data.testbed.fitiotlab import Euratech
        euratech = Euratech()

        super(EuratechAll, self).__init__(
            euratech,
            source_ids={183},
            sink_id=148,
            space_behind_sink=True
        )

class GrenobleSmall(Configuration):
    def __init__(self, *args, **kwargs):
        from data.testbed.fitiotlab import Grenoble
        grenoble = Grenoble(subset=[(86, 93), (129, 137), (160, 168), (186, 193)])

        super(GrenobleSmall, self).__init__(
            grenoble,
            source_ids={187},
            sink_id=134,
            space_behind_sink=False
        )

class GrenobleAll(Configuration):
    """A source in the corner and a sink in the centre."""
    def __init__(self, *args, **kwargs):
        from data.testbed.fitiotlab import Grenoble
        grenoble = Grenoble()

        super(GrenobleAll, self).__init__(
            grenoble,
            source_ids={10},
            sink_id=80,
            space_behind_sink=True
        )


class TwistGuess(Configuration):
    def __init__(self, *args, **kwargs):
        from data.testbed.twist import Twist
        twist = Twist()

        super(TwistGuess, self).__init__(
            twist,
            source_ids={11},
            sink_id=210,
            space_behind_sink=False
        )

def configurations():
    """A list of the available configuration classes."""
    return [cls for cls in Configuration.__subclasses__()] # pylint: disable=no-member

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
def create_specific(name, *args, **kwargs):
    confs = [cls for cls in configurations() if cls.__name__ == name]

    if len(confs) == 0:
        raise RuntimeError("No configurations were found using the name {}, args {}".format(name, args))

    if len(confs) > 1:
        raise RuntimeError("There are multiple configurations that have the name {}, not sure which one to choose".format(name))

    return confs[0](*args, **kwargs)

def create(name, args):
    req_attrs = ("network_size", "distance", "node_id_order", "seed")

    if all(hasattr(args, attr_name) for attr_name in req_attrs):
        pos_args = tuple(getattr(args, attr_name) for attr_name in req_attrs)
    else:
        pos_args = tuple()

    kwargs = {}

    return create_specific(name, *pos_args, **kwargs)
