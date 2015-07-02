import os, random, itertools
from scipy.spatial.distance import euclidean

class Line:
    def __init__(self, size, distance, initial_position=10.0):
        self.size = size
        self.distance = distance

        y = 0

        self.nodes = [
            (float(x * distance + initial_position), float(y * distance + initial_position))
            for x in xrange(size)
        ]

        self.centre_node = self.nodes[(len(self.nodes) - 1) / 2]

    def __str__(self):
        return "Line<size={}>".format(self.size)

class Grid:
    def __init__(self, size, distance, initial_position=10.0):
        self.size = size
        self.distance = distance

        self.nodes = [
            (float(x * distance + initial_position), float(y * distance + initial_position))
            for y in xrange(size)
            for x in xrange(size)
        ]

        self.centre_node = self.nodes[(len(self.nodes) - 1) / 2]

    def __str__(self):
        return "Grid<size={}>".format(self.size)

class Circle:
    def __init__(self, diameter, distance, initial_position=10.0):
        self.diameter_in_hops = diameter
        self.diameter = self.diameter_in_hops * distance
        self.distance = distance

        self.nodes = [
            (float(x * distance + initial_position), float(y * distance + initial_position))
            for y in xrange(diameter)
            for x in xrange(diameter)
        ]

        self.centre_node = (len(self.nodes) - 1) / 2

        centre_node_pos = self.nodes[self.centre_node]

        def in_circle(position):
            return euclidean(centre_node_pos, position) < self.diameter / 2.0

        self.nodes = [pos for pos in self.nodes if in_circle(pos)]

    def __str__(self):
        return "Circle<diameter={}>".format(self.diameter_in_hops)

class Ring:
    def __init__(self, diameter, distance, initial_position=10.0):
        self.diameter = diameter
        self.distance = distance

        self.nodes = [
            (float(x * distance + initial_position), float(y * distance + initial_position))
            for y in xrange(diameter)
            for x in xrange(diameter)
            if (x == 0 or x == diameter -1) or (y == 0 or y == diameter - 1)
        ]

    def __str__(self):
        return "Ring<diameter={}>".format(self.diameter)

class SimpleTree:
    """Creates a tree with a single branch."""
    def __init__(self, size, distance, initial_position=10.0):
        self.size = size
        self.distance = distance

        self.nodes = [
            (float(x * distance + initial_position), float(y * distance + initial_position))
            for y in xrange(size)
            for x in xrange(size)
            if (y == 0 or x == (size - 1) / 2)
        ]

        self.centre_node = self.nodes[(len(self.nodes) - 1) / 2]

    def __str__(self):
        return "SimpleTree<size={}>".format(self.size)

class Random:
    def __init__(self, network_size, distance, seed=3, initial_position=10.0):
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
            return (
                rnd.uniform(min_x_pos, max_x_pos),
                rnd.uniform(min_y_pos, max_y_pos)
            )

        def check_nodes(node):
            """All nodes must not be closer than 1m, as TOSSIM doesn't allow this."""
            return all(
                euclidean(node, other_node) > 1.0
                for other_node
                in self.nodes
            )

        max_retries = 20

        self.nodes = []
        for i in xrange(network_size ** 2):
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
