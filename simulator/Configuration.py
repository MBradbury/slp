
from scipy.sparse.csgraph import shortest_path
from scipy.spatial.distance import cdist

from simulator.Topology import Line, Grid, Circle, Random, RandomPoissonDisk, SimpleTree, Ring, TopologyId, OrderedId, IndexId

class InvalidSinkError(RuntimeError):
    def __init__(self, sink_id, sink_ids):
        super().__init__(f"Invalid sink ({sink_id} not in {sink_ids})")

class InvalidSourceError(RuntimeError):
    def __init__(self, source_id, source_ids):
        super().__init__(f"Invalid source ({source_id} not in {source_ids})")

class Configuration(object):
    def __init__(self, topology, source_ids, sink_ids, space_behind_sink):
        super().__init__()

        self.topology = topology
        self.sink_ids = {topology.t2o(TopologyId(sink_id)) for sink_id in sink_ids}
        self.source_ids = {topology.t2o(TopologyId(source_id)) for source_id in source_ids}
        self.space_behind_sink = space_behind_sink

        if any(sink_id.nid < 0 for sink_id in self.sink_ids):
            raise RuntimeError("All sink ids must be positive")

        if any(source_id.nid < 0 for source_id in self.source_ids):
            raise RuntimeError("All source ids must be positive")

        if any(sink_id not in topology.nodes for sink_id in self.sink_ids):
            raise RuntimeError(f"The a sink id {self.sink_ids} is not present in the available node ids {topology.nodes}")

        if any(source_id not in topology.nodes for source_id in self.source_ids):
            raise RuntimeError(f"The a source id {self.source_ids} is not present in the available node ids {topology.nodes}")

        if len(self.sink_ids) == 0:
            raise RuntimeError("There must be at least one sink in the configuration")

        if len(self.source_ids) == 0:
            raise RuntimeError("There must be at least one source in the configuration")

        self._dist_matrix = None
        self._dist_matrix_meters = None
        self._predecessors = None

        self._build_connectivity_matrix()

    def build_arguments(self):
        build_arguments = {
            "SINK_NODE_IDS": "{" + ",".join(str(self.topology.o2t(sink_id)) for sink_id in self.sink_ids) + "}",

            # As a node with node id x will be stored in C arrays at x,
            # we need x + 1 nodes to be specified with tossim
            "MAX_TOSSIM_NODES": max(oid.nid for oid in self.topology.nodes) + 1,
        }

        if self.space_behind_sink:
            build_arguments["SPACE_BEHIND_SINK"] = "1"
        else:
            build_arguments["NO_SPACE_BEHIND_SINK"] = "1"

        return build_arguments

    def __str__(self):
        return f"Configuration<sink_ids={self.sink_ids}, source_ids={self.source_ids}, space_behind_sink={self.space_behind_sink}, topology={self.topology}>"

    def _build_connectivity_matrix(self):
        coords = list(self.topology.nodes.values())

        self._dist_matrix_meters = cdist(coords, coords, 'euclidean')

        # If there is not a uniform distance between nodes,
        # then we cannot build the connectivity matrix this way
        if not hasattr(self.topology, "distance"):
            return

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
        o2i = self.topology.o2i

        i = o2i(ordered_nidi).nid
        j = o2i(ordered_nidj).nid

        return self._dist_matrix[i,j]

    def ssd(self, sink_id, source_id):
        """The number of hops between the sink and the specified source node"""
        if sink_id not in self.sink_ids:
            raise InvalidSinkError(sink_id, self.sink_ids)
        if source_id not in self.source_ids:
            raise InvalidSourceError(source_id, self.source_ids)

        return self.node_distance(sink_id, source_id)

    def node_sink_distance(self, ordered_nid, sink_id):
        """The number of hops between the sink and the specified node"""
        if sink_id not in self.sink_ids:
            raise InvalidSinkError(sink_id, self.sink_ids)

        return self.node_distance(ordered_nid, sink_id)

    def node_source_distance(self, ordered_nid, source_id):
        """The number of hops between the specified source and the specified node"""
        if source_id not in self.source_ids:
            raise InvalidSourceError(source_id, self.source_ids)

        return self.node_distance(ordered_nid, source_id)

    def node_distance_meters(self, ordered_nidi, ordered_nidj):
        """Get the distance between two ordered nodes in meters."""
        o2i = self.topology.o2i

        i = o2i(ordered_nidi).nid
        j = o2i(ordered_nidj).nid

        return self._dist_matrix_meters[i,j]

    def ssd_meters(self, sink_id, source_id):
        """The number of meters between the sink and the specified source node"""
        if sink_id not in self.sink_ids:
            raise InvalidSinkError(sink_id, self.sink_ids)
        if source_id not in self.source_ids:
            raise InvalidSourceError(source_id, self.source_ids)

        return self.node_distance_meters(sink_id, source_id)

    def node_sink_distance_meters(self, node, sink_id):
        """The number of meters between the sink and the specified node"""
        if sink_id not in self.sink_ids:
            raise InvalidSinkError(sink_id, self.sink_ids)

        return self.topology.node_distance_meters(node, sink_id)

    def node_source_distance_meters(self, node, source_id):
        """The number of meters between the specified source and the specified node"""
        if source_id not in self.source_ids:
            raise InvalidSourceError(source_id, self.source_ids)

        return self.topology.node_distance_meters(node, source_id)



    def shortest_path(self, node_from, node_to):
        """Returns a list of nodes that will take you from node_from to node_to along the shortest path."""

        from_idx = self.topology.o2i(node_from)
        to_idx = self.topology.o2i(node_to)

        path = []

        # Start at the end
        node_idx = to_idx

        while node_idx != from_idx:
            # Add current node to path
            node = self.topology.i2o(node_idx)
            path.append(node)

            # Get next in path
            node_idx = IndexId(self._predecessors[from_idx.nid, node_idx.nid])

        # Add final node to path
        node = self.topology.o2i(node_idx)
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
            topo_node_id = TopologyId(int(topo_node_id_str))

            # Check valid node
            ord_node_id = self.topology.t2o(topo_node_id)
            if ord_node_id not in self.topology.nodes:
                raise RuntimeError(f"The node id {topo_node_id} is not a valid node id")

            return topo_node_id

        except ValueError:
            attr_sources = (self, self.topology)
            for attr_source in attr_sources:
                if hasattr(attr_source, topo_node_id_str):
                    ord_node_id = getattr(attr_source, topo_node_id_str)

                    return self.topology.o2t(ord_node_id)

                # For sink_id and source_id look for plurals of them
                # Then make sure there is only one to choose from
                if hasattr(attr_source, topo_node_id_str + "s"):
                    ord_node_ids = getattr(attr_source, topo_node_id_str + "s")

                    if len(ord_node_ids) != 1:
                        raise RuntimeError(f"Unable to get a {topo_node_id_str} because there is not only one of them.")

                    ord_node_id = next(iter(ord_node_ids))

                    return self.topology.o2t(ord_node_id)

            choices = [x for a in (self, self.topology) for x in dir(a) if not callable(getattr(a, x)) and not x.startswith("_")]

            import difflib

            close = difflib.get_close_matches(topo_node_id_str, choices, n=5)
            if len(close) == 0:
                close = choices

            raise RuntimeError(f"No way to work out node from '{topo_node_id_str}', did you mean one of {close}.")

# Coordinates are specified in topology format below

class LineSinkCentre(Configuration):
    def __init__(self, *args, **kwargs):
        line = Line(*args, **kwargs)

        super().__init__(
            line,
            source_ids={0},
            sink_ids={(len(line.nodes) - 1) // 2},
            space_behind_sink=True
        )

class SimpleTreeSinkEnd(Configuration):
    def __init__(self, *args, **kwargs):
        tree = SimpleTree(*args, **kwargs)

        super().__init__(
            tree,
            source_ids={0},
            sink_ids={tree.size - 1},
            space_behind_sink=True
        )

class SourceCorner(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={0},
            sink_ids={(len(grid.nodes) - 1) // 2},
            space_behind_sink=True
        )

class Source2CornerTop(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={0, 2},
            sink_ids={(len(grid.nodes) - 1) // 2},
            space_behind_sink=True
        )

class Source3CornerTop(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={0, 2, grid.size+1},
            sink_ids={(len(grid.nodes) - 1) // 2},
            space_behind_sink=True
        )

class Source3CornerTopLinear(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={0, 2, 4},
            sink_ids={(len(grid.nodes) - 1) // 2},
            space_behind_sink=True
        )

class SinkCorner(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={(len(grid.nodes) - 1) // 2},
            sink_ids={len(grid.nodes) - 1},
            space_behind_sink=False
        )

class SinkCorner2Source(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={(len(grid.nodes) - 1)//2 - 1, (len(grid.nodes) - 1)//2 + 1},
            sink_ids={len(grid.nodes) - 1},
            space_behind_sink=False
        )

class SinkCorner3Source(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={(len(grid.nodes) - 1)//2 - 1, (len(grid.nodes) - 1)//2 + 1, (len(grid.nodes) - 1) // 2 + grid.size},
            sink_ids={len(grid.nodes) - 1},
            space_behind_sink=False
        )

class SinkCorner3SourceLinear(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={(len(grid.nodes) - 1)//2 - 2, (len(grid.nodes) - 1)//2, (len(grid.nodes) - 1)//2 + 2},
            sink_ids={len(grid.nodes) - 1},
            space_behind_sink=False
        )

class FurtherSinkCorner(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={0},
            sink_ids={len(grid.nodes) - 1},
            space_behind_sink=False
        )
class FurtherSinkCorner2Source(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={0, 2},
            sink_ids={len(grid.nodes) - 1},
            space_behind_sink=False
        )
class FurtherSinkCorner3Source(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={0, 2, grid.size+1},
            sink_ids={len(grid.nodes) - 1},
            space_behind_sink=False
        )

class FurtherSinkCorner3SourceLinear(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={0, 2, 4},
            sink_ids={len(grid.nodes) - 1},
            space_behind_sink=False
        )

class SinkSourceOpposite(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={(grid.size * 2) + 2},
            sink_ids={(grid.size * (grid.size - 2)) - 2 - 1},
            space_behind_sink=True
        )

class SinkSourceOpposite2Source(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={(grid.size * 2) + 2, (grid.size * 2) + 4},
            sink_ids={(grid.size * (grid.size - 2)) - 2 - 1},
            space_behind_sink=True
        )

class SinkSourceOpposite3Source(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={(grid.size * 2) + 2, (grid.size * 2) + 4, (grid.size * 2) + grid.size + 3},
            sink_ids={(grid.size * (grid.size - 2)) - 2 - 1},
            space_behind_sink=True
        )

class Generic1(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)
        node_count = len(grid.nodes)

        super().__init__(
            grid,
            source_ids={(node_count // 2) - (grid.size // 3)},
            sink_ids={(node_count // 2) + (grid.size // 3)},
            space_behind_sink=False
        )

class Generic2(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={(grid.size * (grid.size - 2)) - 2 - 1},
            sink_ids={(grid.size * 2) + 2},
            space_behind_sink=True
        )

class RingTop(Configuration):
    def __init__(self, *args, **kwargs):
        ring = Ring(*args, **kwargs)

        super().__init__(
            ring,
            source_ids={ring.diameter - 1},
            sink_ids={0},
            space_behind_sink=True
        )

class RingMiddle(Configuration):
    def __init__(self, *args, **kwargs):
        ring = Ring(*args, **kwargs)

        super().__init__(
            ring,
            source_ids={(4 * ring.diameter - 5) // 2 + 1},
            sink_ids={(4 * ring.diameter - 5) // 2},
            space_behind_sink=True
        )

class RingOpposite(Configuration):
    def __init__(self, *args, **kwargs):
        ring = Ring(*args, **kwargs)

        super().__init__(
            ring,
            source_ids={len(ring.nodes) - 1},
            sink_ids={0},
            space_behind_sink=True
        )

class CircleSinkCentre(Configuration):
    def __init__(self, *args, **kwargs):
        circle = Circle(*args, **kwargs)

        super().__init__(
            circle,
            source_ids={5},
            sink_ids={circle.ordered_nid_to_topology_nid[circle.centre_node]},
            space_behind_sink=True
        )

class CircleSourceCentre(Configuration):
    def __init__(self, *args, **kwargs):
        circle = Circle(*args, **kwargs)

        super().__init__(
            circle,
            source_ids={circle.ordered_nid_to_topology_nid[circle.centre_node]},
            sink_ids={5},
            space_behind_sink=False
        )

class CircleEdges(Configuration):
    def __init__(self, *args, **kwargs):
        circle = Circle(*args, **kwargs)

        super().__init__(
            circle,
            source_ids={len(circle.nodes) - 5 - 1},
            sink_ids={5},
            space_behind_sink=False
        )

class Source2Corners(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={0, len(grid.nodes) - 1},
            sink_ids={(len(grid.nodes) - 1) // 2},
            space_behind_sink=True
        )

class Source3Corners(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={grid.size - 1, len(grid.nodes) - grid.size, len(grid.nodes) - 1},
            sink_ids={(len(grid.nodes) - 1) // 2},
            space_behind_sink=False
        )

class Source4Corners(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={0, grid.size - 1, len(grid.nodes) - grid.size, len(grid.nodes) - 1},
            sink_ids={(len(grid.nodes) - 1) // 2},
            space_behind_sink=False
        )

class Source2Edges(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={
                (grid.size - 1) // 2,
                len(grid.nodes) - ((grid.size - 1) // 2) - 1
            },
            sink_ids={(len(grid.nodes) - 1) // 2},
            space_behind_sink=True
        )

class Source4Edges(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={
                (grid.size - 1) // 2,

                ((len(grid.nodes) - 1) // 2) - (grid.size - 1) // 2,
                ((len(grid.nodes) - 1) // 2) + (grid.size - 1) // 2,

                len(grid.nodes) - ((grid.size - 1) // 2) - 1
            },
            sink_ids={(len(grid.nodes) - 1) // 2},
            space_behind_sink=True
        )

class Source2Corner(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={3, grid.size * 3},
            sink_ids={(len(grid.nodes) - 1) // 2},
            space_behind_sink=True
        )

class FurtherSinkSource2Corner(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={3, grid.size * 3},
            sink_ids={len(grid.nodes) - 1},
            space_behind_sink=True
        )

class Source3Corner(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={0, 3, grid.size * 3},
            sink_ids={(len(grid.nodes) - 1) // 2},
            space_behind_sink=True
        )

class Source2Corner2OppositeCorner(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={
                3,
                grid.size * 3,
                len(grid.nodes) - (grid.size * 3) - 1,
                len(grid.nodes) - 4,
            },
            sink_ids={(len(grid.nodes) - 1) // 2},
            space_behind_sink=True
        )

class SourceEdgeCorner(Configuration):
    def __init__(self, *args, **kwargs):
        grid = Grid(*args, **kwargs)

        super().__init__(
            grid,
            source_ids={
                ((len(grid.nodes) - 1) // 2) + (grid.size - 1) // 2,
                len(grid.nodes) - 1
            },
            sink_ids={(len(grid.nodes) - 1) // 2},
            space_behind_sink=True
        )

class RandomConnected(Configuration):
    def __init__(self, *args, **kwargs):
        random = Random(*args, **kwargs)

        super().__init__(
            random,
            source_ids={len(random.nodes) - 1},
            sink_ids={0},
            space_behind_sink=True
        )

class RandomPoissonDiskConnected(Configuration):
    def __init__(self, *args, **kwargs):
        random = RandomPoissonDisk(*args, **kwargs)

        super().__init__(
            random,
            source_ids={len(random.nodes) - 1},
            sink_ids={len(random.nodes) // 2},
            space_behind_sink=True
        )

class RandomPoissonDiskConnectedSeed2(Configuration):
    def __init__(self, *args, **kwargs):
        new_kwargs = {**kwargs, "seed": 2}
        try:
            random = RandomPoissonDisk(*args, **new_kwargs)
        except TypeError:
            # Try without seed in args
            random = RandomPoissonDisk(*args[:-1], **new_kwargs)

        super().__init__(
            random,
            source_ids={len(random.nodes) - 1},
            sink_ids={len(random.nodes) // 2},
            space_behind_sink=True
        )

class IndriyaOneFloorSrc31Sink15(Configuration):
    def __init__(self):
        from data.testbed.indriya import Indriya
        indriya = Indriya()

        super().__init__(
            indriya,
            source_ids={31},
            sink_ids={15},
            space_behind_sink=True
        )

class IndriyaTwoFloorsSrc31Sink60(Configuration):
    def __init__(self):
        from data.testbed.indriya import Indriya
        indriya = Indriya()

        super().__init__(
            indriya,
            source_ids={31},
            sink_ids={60},
            space_behind_sink=True
        )

class EuratechSinkCentre(Configuration):
    def __init__(self):
        from data.testbed.fitiotlab import Euratech
        euratech = Euratech()

        super().__init__(
            euratech,
            source_ids={98},
            sink_ids={153},
            space_behind_sink=True
        )

class FlockLabSinkCentre(Configuration):
    def __init__(self):
        from data.testbed.flocklab import FlockLab
        flocklab = FlockLab()

        super().__init__(
            flocklab,
            source_ids={1},
            sink_ids={23},
            space_behind_sink=True
        )

def configurations():
    """A list of the available configuration classes."""
    return Configuration.__subclasses__() # pylint: disable=no-member

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

def try_create_specific(name):
    # The format of this name should be:
    # <Topology><Source><number><Sink><Number>

    import re

    from data.testbed.indriya import Indriya
    from data.testbed.fitiotlab import Euratech
    from data.testbed.fitiotlab import Rennes
    from data.testbed.twist import Twist
    from data.testbed.flocklab import FlockLab

    available_topologies = [
        Line, Grid, Circle, Random, SimpleTree, Ring,
        Euratech, Rennes, Indriya, Twist, FlockLab
    ]

    match = re.match(r"^([A-Za-z]+)Source([0-9]+)Sink([0-9]+)$", name)
    if not match:
        raise RuntimeError(f"Unable to parse configuration name {name}")

    (topology_name, source_id, sink_id) = match.groups()

    topology_classes = [t for t in available_topologies if t.__name__ == topology_name]

    if len(topology_classes) == 0:
        raise RuntimeError(f"Unable to find a topology called {topology_name}")

    topology_class = topology_classes[0]

    class NewConfiguration(Configuration):
        def __init__(self, *args, **kwargs):
            super().__init__(
                topology_class(),
                source_ids={int(source_id)},
                sink_ids={int(sink_id)},
                space_behind_sink=False
            )

    NewConfiguration.__name__ = name

    return NewConfiguration


def create_specific(name, *args, **kwargs):
    confs = [cls for cls in configurations() if cls.__name__ == name]

    if len(confs) > 1:
        raise RuntimeError(f"There are multiple configurations that have the name {name}, not sure which one to choose")

    # Sometimes we might want to be able to dynamically create configurations
    if len(confs) == 0:
        try:
            conf_class = try_create_specific(name)
        except BaseException as ex:
            raise RuntimeError(f"No configurations were found using the name {name}. Tried to create a Configuration, but this failed.", ex)
    else:
        conf_class = confs[0]

    try:
        return conf_class(*args, **kwargs)
    except TypeError:
        return conf_class(*args)

def create(name, args):
    req_attrs = ("network_size", "distance", "node_id_order")
    kwd_attrs = ("seed",)

    pos_args = tuple()
    kwargs = {}

    if isinstance(args, dict):
        req_attrs = [attr_name.replace("_", " ") for attr_name in req_attrs]
        kwd_attrs = [attr_name.replace("_", " ") for attr_name in kwd_attrs]

        if all(attr_name in args for attr_name in req_attrs):
            pos_args = tuple(args[attr_name] for attr_name in req_attrs)
            kwargs = {attr_name: args[attr_name] for attr_name in kwd_attrs}
    else:
        if all(hasattr(args, attr_name) for attr_name in req_attrs):
            pos_args = tuple(getattr(args, attr_name) for attr_name in req_attrs)
            kwargs = {attr_name: getattr(args, attr_name) for attr_name in kwd_attrs}

    return create_specific(name, *pos_args, **kwargs)
