import os, random, itertools
from scipy.spatial.distance import euclidean

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

class Random:
    def __init__(self, network_size, distance, initial_position=10.0):
        self.seed = random.random()
        self.size = network_size

        rnd = random.Random()
        rnd.seed(self.seed)

        min_x_pos = 0
        min_y_pos = 0
        max_x_pos = network_size * distance * 2
        max_y_pos = network_size * distance * 2

        self.area = ((min_x_pos, max_x_pos), (min_y_pos, max_y_pos))

        min_x_pos += initial_position
        max_x_pos += initial_position
        min_y_pos += initial_position
        max_y_pos += initial_position

        # Due to LinkLayerModel, the distance between nodes must be greater than or equal to 1.

        def random_coordinate():
            return (
                min_x_pos + rnd.random() * ((max_x_pos - min_x_pos) + 1),
                min_y_pos + rnd.random() * ((max_y_pos - min_y_pos) + 1)
            )

        def create_nodes():
            self.nodes = [random_coordinate() for n in xrange(network_size ** 2)]

        def check_nodes():
            return all(
                i == j or euclidean(node1, node2) > 1.0
                for ((i, node1), (j, node2))
                in itertools.product(enumerate(self.nodes), enumerate(self.nodes))
            )

        max_loops = 20

        for loops in xrange(max_loops):
            create_nodes()
            if check_nodes():
                break
        else:
            raise RuntimeError("Unable to allocate a valid set of random node positions in {} loops.".format(max_loops))

    def __str__(self):
        return "Random<seed={},network_size={},area={}>".format(self.seed,self.size, self.area)

def topology_path(module, args):
    if args.mode == "CLUSTER":
        return os.path.join(module.replace(".", "/"), "topology.txt")
    else:
        return "./topology.txt"
