import os
from scipy.spatial.distance import euclidean

class Grid:
    def __init__(self, size, distance, initial_position=10.0):
        self.size = size
        self.distance = distance

        self.nodes = [(float(x * distance + initial_position), float(y * distance + initial_position))
            for y in xrange(size)
            for x in xrange(size)]

        self.centre_node = self.nodes[(len(self.nodes) - 1) / 2]

    def __str__(self):
        return "Grid<size={}>".format(self.size)

class Circle:
    def __init__(self, diameter, distance, initial_position=10.0):
        self.diameter_in_hops = diameter
        self.diameter = self.diameter_in_hops * distance
        self.distance = distance

        self.nodes = [(float(x * distance + initial_position), float(y * distance + initial_position))
            for y in xrange(diameter)
            for x in xrange(diameter)]

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

        self.nodes = [(float(x * distance + initial_position), float(y * distance + initial_position))
            for y in xrange(diameter)
            for x in xrange(diameter)
            if (x == 0 or x == diameter -1) or (y == 0 or y == diameter - 1)]

    def __str__(self):
        return "Ring<diameter={}>".format(self.diameter)

class Random:
    def __init__(self, size_root, initial_position=10.0):
        raise NotImplementedError()

def topology_path(module, args):
    if args.mode == "CLUSTER":
        return os.path.join(module.replace(".", "/"), "topology.txt")
    else:
        return "./topology.txt"
