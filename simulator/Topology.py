import os

import numpy as np

# Use our custom fast euclidean function,
# fallback to the slow scipy version.
try:
    from euclidean import euclidean2_2d
except ImportError:
    from scipy.spatial.distance import euclidean as euclidean2_2d

class Topology(object):
    def __init__(self):
        self.nodes = None

    def node_distance_meters(self, node1, node2):
        return euclidean2_2d(self.nodes[node1], self.nodes[node2])

    @staticmethod
    def coord_distance_meters(coord1, coord2):
        return euclidean2_2d(coord1, coord2)

class Line(Topology):
    def __init__(self, size, distance, initial_position=10.0):
        super(Line, self).__init__()

        self.size = size
        self.distance = distance

        y = 0

        self.nodes = [
            np.array((float(x * distance + initial_position), float(y * distance + initial_position)), dtype=np.float64)
            for x in range(size)
        ]

        self.centre_node = (len(self.nodes) - 1) / 2

    def __str__(self):
        return "Line<size={}>".format(self.size)

class Grid(Topology):
    def __init__(self, size, distance, initial_position=10.0):
        super(Grid, self).__init__()

        self.size = size
        self.distance = distance

        self.nodes = [
            np.array((float(x * distance + initial_position), float(y * distance + initial_position)), dtype=np.float64)
            for y in range(size)
            for x in range(size)
        ]

        self.top_left = 0
        self.top_right = size - 1
        self.centre_node = (len(self.nodes) - 1) / 2
        self.bottom_left = len(self.nodes) - size
        self.bottom_right = len(self.nodes) - 1

    def __str__(self):
        return "Grid<size={}>".format(self.size)

class Circle(Topology):
    def __init__(self, diameter, distance, initial_position=10.0):
        super(Circle, self).__init__()

        self.diameter_in_hops = diameter
        self.diameter = self.diameter_in_hops * distance
        self.distance = distance

        self.nodes = [
            np.array(f(loat(x * distance + initial_position), float(y * distance + initial_position)), dtype=np.float64)
            for y in range(diameter)
            for x in range(diameter)
        ]

        self.centre_node = (len(self.nodes) - 1) / 2

        centre_node_pos = self.nodes[self.centre_node]

        def in_circle(position):
            return self.coord_distance_meters(centre_node_pos, position) < self.diameter / 2.0

        self.nodes = [pos for pos in self.nodes if in_circle(pos)]

    def __str__(self):
        return "Circle<diameter={}>".format(self.diameter_in_hops)

class Ring(Topology):
    def __init__(self, diameter, distance, initial_position=10.0):
        super(Ring, self).__init__()

        self.diameter = diameter
        self.distance = distance

        self.nodes = [
            np.array((float(x * distance + initial_position), float(y * distance + initial_position)), dtype=np.float64)
            for y in range(diameter)
            for x in range(diameter)
            if (x == 0 or x == diameter -1) or (y == 0 or y == diameter - 1)
        ]

    def __str__(self):
        return "Ring<diameter={}>".format(self.diameter)

class SimpleTree(Topology):
    """Creates a tree with a single branch."""
    def __init__(self, size, distance, initial_position=10.0):
        super(SimpleTree, self).__init__()

        self.size = size
        self.distance = distance

        self.nodes = [
            np.array((float(x * distance + initial_position), float(y * distance + initial_position)), dtype=np.float64)
            for y in range(size)
            for x in range(size)
            if (y == 0 or x == (size - 1) / 2)
        ]

    def __str__(self):
        return "SimpleTree<size={}>".format(self.size)

class Random(Topology):
    def __init__(self, network_size, distance, seed=3, initial_position=10.0):
        super(Random, self).__init__()

        import random

        self.seed = seed
        self.size = network_size
        self.distance = distance

        rnd = random.Random()
        rnd.seed(self.seed)

        min_x_pos = initial_position
        min_y_pos = initial_position
        max_x_pos = initial_position + network_size * distance
        max_y_pos = initial_position + network_size * distance

        self.area = ((min_x_pos, max_x_pos), (min_y_pos, max_y_pos))

        def random_coordinate():
            return np.array((
                rnd.uniform(min_x_pos, max_x_pos),
                rnd.uniform(min_y_pos, max_y_pos)
            ), dtype=np.float64)

        def check_nodes(node):
            """All nodes must not be closer than 1m, as TOSSIM doesn't allow this."""
            return all(
                self.coord_distance_meters(node, other_node) > 1.0
                for other_node
                in self.nodes
            )

        max_retries = 20

        self.nodes = []
        for i in range(network_size ** 2):
            coord = None

            for x in range(max_retries):
                coord = random_coordinate()

                if check_nodes(coord):
                    break
            else:
                raise RuntimeError("Unable to allocate random node within {} tries.".format(max_retries))

            self.nodes.append(coord)

    def __str__(self):
        return "Random<seed={},network_size={},area={}>".format(self.seed, self.size, self.area)

class DCSWarwick(Topology):
    """The layout of the nodes in DCS Warwick."""
    def __init__(self, initial_position=10.0):
        super(DCSWarwick, self).__init__()

        floor_distance = 20.0

        self.nodes = [
            np.array((-100, -100), dtype=np.float64), # Padding Node - There is no node 0 in this network

            np.array((floor_distance*2 + 0, 0),   dtype=np.float64), # CS2.01
            np.array((floor_distance*2 + 5, 7),   dtype=np.float64), # CS2.08 (window)
            np.array((floor_distance*2 + 5, 10),  dtype=np.float64), # CS2.08 (shelf)
            np.array((floor_distance*2 + 5, 5),   dtype=np.float64), # CS2.06

            np.array((-100, -100), dtype=np.float64), # Padding Node - There is no node 5 in this network
            
            np.array((floor_distance*1 + 5, 5), dtype=np.float64), # CS1.02 (far end)
            np.array((floor_distance*1 + 5, 10), dtype=np.float64), # CS1.02 (door)
            np.array((floor_distance*2 + 5, 0),   dtype=np.float64), # CS2.02

            #np.array((-1, -1), dtype=np.float64), # Padding Node
            #np.array((-1, -1), dtype=np.float64), # Padding Node
        ]

        # Apply the initial position
        for node in self.nodes:
            node += initial_position

    def __str__(self):
        return "DCSWarwick<>"

class Indriya(Topology):
    """The layout of nodes on the Indriya testbed, see: https://indriya.comp.nus.edu.sg/motelab/html/motes-info.php"""
    def __init__(self, initial_position=10.0):
        super(Indriya, self).__init__()

        floor_distance = 20.0

        self.nodes = [
            np.array((-100, -100), dtype=np.float64), # Padding Node - There is no node 0 in this network
        ]

        self.nodes += [ np.array((-100, -100), dtype=np.float64) ] * (39 + 86)

        # Apply the initial position
        for node in self.nodes:
            node += initial_position

    def __str__(self):
        return "Indriya<>"

def topology_path(module, args):
    if args.mode == "CLUSTER":
        return os.path.join(module.replace(".", "/"), "topology.txt")
    else:
        return "./topology.txt"
