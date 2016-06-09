import os

import numpy as np

class Topology(object):
    def __init__(self):
        self.nodes = None

    def node_distance_meters(self, node1, node2):
        # See: https://stackoverflow.com/questions/1401712/how-can-the-euclidean-distance-be-calculated-with-numpy
        return np.linalg.norm(self.nodes[node1] - self.nodes[node2])

    def coord_distance_meters(self, coord1, coord2):
        return np.linalg.norm(coord1 - coord2)

class Line(Topology):
    def __init__(self, size, distance, initial_position=10.0):
        super(Line, self).__init__()

        self.size = size
        self.distance = distance

        y = 0

        self.nodes = [
            np.array((float(x * distance + initial_position), float(y * distance + initial_position)))
            for x in xrange(size)
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
            np.array((float(x * distance + initial_position), float(y * distance + initial_position)))
            for y in xrange(size)
            for x in xrange(size)
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
            np.array(f(loat(x * distance + initial_position), float(y * distance + initial_position)))
            for y in xrange(diameter)
            for x in xrange(diameter)
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
            np.array((float(x * distance + initial_position), float(y * distance + initial_position)))
            for y in xrange(diameter)
            for x in xrange(diameter)
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
            np.array((float(x * distance + initial_position), float(y * distance + initial_position)))
            for y in xrange(size)
            for x in xrange(size)
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
            ))

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

            for x in xrange(max_retries):
                coord = random_coordinate()

                if check_nodes(coord):
                    break
            else:
                raise RuntimeError("Unable to allocate random node within {} tries.".format(max_retries))

            self.nodes.append(coord)

    def __str__(self):
        return "Random<seed={},network_size={},area={}>".format(self.seed, self.size, self.area)

def topology_path(module, args):
    if args.mode == "CLUSTER":
        return os.path.join(module.replace(".", "/"), "topology.txt")
    else:
        return "./topology.txt"
