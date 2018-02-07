
from collections import OrderedDict
from functools import total_ordering
import itertools
import random

import numpy as np

# Use our custom fast euclidean function,
# fallback to the slow scipy version.
try:
    from euclidean import euclidean2_2d
except ImportError:
    from scipy.spatial.distance import euclidean as euclidean2_2d

@total_ordering
class NodeId(object):
    __slots__ = ("nid",)

    def __init__(self, nid):
        if not isinstance(nid, (int, np.int_)):
            raise TypeError("nid is not an int it is a", type(nid))

        self.nid = nid

    def __hash__(self):
        return hash(self.nid)

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.nid == other.nid

    def __ne__(self, other):
        return not (self == other)

    def __le__(self, other):
        return self.nid < other.nid

    def __repr__(self):
        return repr(self.nid)

class OrderedId(NodeId):
    def __init__(self, nid):
        if isinstance(nid, OrderedId):
            nid = nid.nid
        super(OrderedId, self).__init__(nid)

class TopologyId(NodeId):
    def __init__(self, nid):
        if isinstance(nid, TopologyId):
            nid = nid.nid
        super(TopologyId, self).__init__(nid)

class IndexId(NodeId):
    def __init__(self, nid):
        if isinstance(nid, IndexId):
            nid = nid.nid
        super(IndexId, self).__init__(nid)

class Topology(object):
    def __init__(self, seed=None):
        self.nodes = OrderedDict()
        self.topology_nid_to_ordered_nid = {}
        self.ordered_nid_to_topology_nid = {}
        self.keys = []
        self.ordered_ids = []
        self.ordered_ids_reverse_mapping = {}
        self.seed = seed

    def node_distance_meters(self, node1, node2):
        if not isinstance(node1, OrderedId):
            raise TypeError("node1 is not an OrderedId it is a", type(node1))

        if not isinstance(node2, OrderedId):
            raise TypeError("node2 is not an OrderedId it is a", type(node2))

        """Gets the node distance in meters using ordered node ids"""
        return euclidean2_2d(self.nodes[node1], self.nodes[node2])

    @staticmethod
    def coord_distance_meters(coord1, coord2):
        return euclidean2_2d(coord1, coord2)

    def o2t(self, ordered_nid):
        """Converts a ordered node id to a topology node id"""
        if not isinstance(ordered_nid, OrderedId):
            raise TypeError("ordered_nid is not an OrderedId it is a", type(ordered_nid))

        return self.ordered_nid_to_topology_nid[ordered_nid]

    def t2o(self, topology_nid):
        """Converts an topology node id to an ordered node id"""
        if not isinstance(topology_nid, TopologyId):
            raise TypeError("topology_nid is not an TopologyId it is a", type(topology_nid))

        return self.topology_nid_to_ordered_nid[topology_nid]

    def o2i(self, ordered_nid):
        """Get the index that an ordered node id will be stored in"""
        if not isinstance(ordered_nid, OrderedId):
            raise TypeError("ordered_nid is not an OrderedId it is a", type(ordered_nid))

        return self.ordered_ids_reverse_mapping[ordered_nid]

    def i2o(self, node_idx):
        """Get the ordered node id from a node index"""
        if not isinstance(node_idx, IndexId):
            raise TypeError("node_idx is not an IndexId it is a", type(node_idx).name)

        return self.ordered_ids[node_idx.nid]

    def _process_node_id_order(self, node_id_order):
        if node_id_order == "topology":

            self.topology_nid_to_ordered_nid = {TopologyId(nid): OrderedId(nid) for nid in self.nodes.keys()}
            self.ordered_nid_to_topology_nid = {OrderedId(nid): TopologyId(nid) for nid in self.nodes.keys()}

        elif node_id_order == "randomised":

            if self.seed is None:
                raise RuntimeError("Need to have a non-None seed to randomise the node id order of a topology")

            rnd = random.Random()
            rnd.seed(self.seed)

            nids = list(self.nodes.keys())
            shuffled_nids = list(range(len(self.nodes.keys())))  # Provides sequential randomised ids

            rnd.shuffle(shuffled_nids)

            self.topology_nid_to_ordered_nid = {TopologyId(nid): OrderedId(shuffled_nid) for (nid, shuffled_nid) in zip(nids, shuffled_nids)}
            self.ordered_nid_to_topology_nid = {OrderedId(shuffled_nid): TopologyId(nid) for (nid, shuffled_nid) in zip(nids, shuffled_nids)}

        else:
            raise RuntimeError(f"Unknown node id order {node_id_order}")

        new_nodes = OrderedDict()

        for (nid, loc) in self.nodes.items():
            new_nodes[self.t2o(TopologyId(nid))] = loc

        self.nodes = new_nodes

        self.ordered_ids = list(self.nodes.keys())
        self.ordered_ids_reverse_mapping = {nid: IndexId(idx) for (idx, nid) in enumerate(self.ordered_ids)}

class Line(Topology):
    def __init__(self, size, distance, node_id_order, seed=None):
        super(Line, self).__init__(seed)

        self.size = size
        self.distance = float(distance)

        y = 0

        for x in range(size):
            self.nodes[x] = np.array((x * distance, y * distance), dtype=np.float64)

        self._process_node_id_order(node_id_order)

        self.centre_node = self.t2o(TopologyId((len(self.nodes) - 1) // 2))

    def __str__(self):
        return f"Line<size={self.size}>"

class Grid(Topology):
    def __init__(self, size, distance, node_id_order, seed=None):
        super(Grid, self).__init__(seed)

        self.size = size
        self.distance = float(distance)

        line = list(range(size))

        for (nid, (y, x)) in enumerate(itertools.product(line, line)):
            self.nodes[nid] = np.array((x * distance, y * distance), dtype=np.float64)

        self._process_node_id_order(node_id_order)

        self.top_left = self.t2o(TopologyId(0))
        self.top_right = self.t2o(TopologyId(size - 1))
        self.centre_node = self.t2o(TopologyId((len(self.nodes) - 1) // 2))
        self.bottom_left = self.t2o(TopologyId(len(self.nodes) - size))
        self.bottom_right = self.t2o(TopologyId(len(self.nodes) - 1))

    def __str__(self):
        return f"Grid<size={self.size}>"

class Circle(Topology):
    def __init__(self, diameter, distance, node_id_order, seed=None):
        super(Circle, self).__init__(seed)

        self.diameter_in_hops = diameter
        self.diameter = self.diameter_in_hops * distance
        self.distance = float(distance)

        line = list(range(diameter))

        mid_point = (diameter - 1) / 2
        centre_node_pos = np.array((mid_point * distance, mid_point * distance), dtype=np.float64)

        for (y, x) in itertools.product(line, line):

            position = np.array((x * distance, y * distance), dtype=np.float64)

            dist = self.coord_distance_meters(centre_node_pos, position)

            if dist <= self.diameter / 2.0:
                nid = len(self.nodes)

                self.nodes[nid] = position

                if np.isclose(dist, 0):
                    self.centre_node = nid

        self._process_node_id_order(node_id_order)

        self.centre_node = self.t2o(self.centre_node)

    def __str__(self):
        return f"Circle<diameter={self.diameter_in_hops}>"

class Ring(Topology):
    def __init__(self, diameter, distance, node_id_order, seed=None):
        super(Ring, self).__init__(seed)

        self.diameter = diameter
        self.distance = float(distance)

        line = list(range(diameter))

        for (nid, (y, x)) in enumerate(itertools.product(line, line)):
            if (x == 0 or x == diameter - 1) or (y == 0 or y == diameter - 1):
                self.nodes[nid] = np.array((x * distance, y * distance), dtype=np.float64)

        self._process_node_id_order(node_id_order)

    def __str__(self):
        return f"Ring<diameter={self.diameter}>"

class SimpleTree(Topology):
    """Creates a tree with a single branch."""
    def __init__(self, size, distance, node_id_order, seed=None):
        super(SimpleTree, self).__init__(seed)

        self.size = size
        self.distance = float(distance)

        line = list(range(size))

        for (nid, (y, x)) in enumerate(itertools.product(line, line)):
            if y == 0 or x == (size - 1) / 2:
                self.nodes[nid] = np.array((x * distance, y * distance), dtype=np.float64)

        self._process_node_id_order(node_id_order)

    def __str__(self):
        return f"SimpleTree<size={self.size}>"

class Random(Topology):
    def __init__(self, network_size, distance, node_id_order, seed=None):
        super(Random, self).__init__(seed)

        if seed is None:
            raise RuntimeError(f"{type(self)} must have a non None seed")

        self.size = network_size
        self.distance = float(distance)

        rnd = random.Random()
        rnd.seed(self.seed)

        min_x_pos = 0
        min_y_pos = 0
        max_x_pos = network_size * distance
        max_y_pos = network_size * distance

        self.area = ((min_x_pos, max_x_pos), (min_y_pos, max_y_pos))

        def random_coordinate():
            """Get a random 2D coordinate within the min and max, x and y coords"""
            return np.array((
                rnd.uniform(min_x_pos, max_x_pos),
                rnd.uniform(min_y_pos, max_y_pos)
            ), dtype=np.float64)

        def check_nodes(node):
            """All nodes must not be closer than 1m, as TOSSIM doesn't allow this."""
            return all(
                self.coord_distance_meters(node, other_node) > 1.0
                for other_node
                in self.nodes.values()
            )

        max_retries = 20

        for i in range(network_size ** 2):
            coord = None

            for x in range(max_retries):
                coord = random_coordinate()

                if check_nodes(coord):
                    break
            else:
                raise RuntimeError(f"Unable to allocate random node within {max_retries} tries.")

            self.nodes[i] = coord

        # No need to randomise node ids here
        self._process_node_id_order("topology")

    def __str__(self):
        return f"Random<seed={self.seed},network_size={self.size},area={self.area}>"

class RandomPoissonDisk(Topology):
    def __init__(self, network_size, distance, node_id_order, seed=None):
        super(RandomPoissonDisk, self).__init__(seed)

        from bridson import poisson_disc_samples

        if seed is None:
            raise RuntimeError(f"{type(self)} must have a non None seed")

        self.size = network_size
        self.distance = float(distance)

        rnd = random.Random()
        rnd.seed(self.seed)

        min_x_pos = 0
        min_y_pos = 0
        max_x_pos = network_size * distance * 1.25
        max_y_pos = network_size * distance * 1.25

        self.area = ((min_x_pos, max_x_pos), (min_y_pos, max_y_pos))

        samples = poisson_disc_samples(width=max_x_pos, height=max_y_pos, r=distance * 0.6, random=rnd.random)

        for (i, coord) in zip(range(network_size**2), samples):
            self.nodes[i] = np.array(coord, dtype=np.float64)

        if len(self.nodes) != network_size**2:
            raise RuntimeError(f"Incorrect network size of {len(self.nodes)}, expected {network_size**2}")

        self._process_node_id_order(node_id_order)

    def __str__(self):
        return f"RandomPoissonDisk<seed={self.seed},network_size={self.size},area={self.area}>"
