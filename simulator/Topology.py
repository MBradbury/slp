import os
from scipy.spatial.distance import euclidean

class Grid:
	def __init__(self, size, distance, initialPosition=10.0):
		self.size = size
		self.distance = distance

		self.nodes = [(float(x * distance + initialPosition), float(y * distance + initialPosition))
			for y in xrange(size)
			for x in xrange(size)]

		self.centreNode = self.nodes[(len(self.nodes) - 1) / 2]

	def __str__(self):
		return "Grid<size={}>".format(self.size)

class Circle:
	def __init__(self, diameter, distance, initialPosition=10.0):
		self.diameterInHops = diameter
		self.diameter = self.diameterInHops * distance
		self.distance = distance

		self.nodes = [(float(x * distance + initialPosition), float(y * distance + initialPosition))
			for y in xrange(diameter)
			for x in xrange(diameter)]

		self.centreNode = (len(self.nodes) - 1) / 2

		centreNodePos = self.nodes[self.centreNode]

		def isInCircle(position):
			return euclidean(centreNodePos, position) < self.diameter / 2.0

		self.nodes = [pos for pos in self.nodes if isInCircle(pos)]

	def __str__(self):
		return "Circle<diameter={}>".format(self.diameterInHops)

class Ring:
	def __init__(self, diameter, distance, initialPosition=10.0):
		self.diameter = diameter
		self.distance = distance

		self.nodes = [(float(x * distance + initialPosition), float(y * distance + initialPosition))
			for y in xrange(diameter)
			for x in xrange(diameter)
			if (x == 0 or x == diameter -1) or (y == 0 or y == diameter - 1)]

	def __str__(self):
		return "Ring<diameter={}>".format(self.diameter)

class Random:
	def __init__(self, sizeRoot, initialPosition=10.0):
		raise Exception("TODO")

def topology_path(module, args):
	if args.mode == "CLUSTER":
		return os.path.join(module.replace(".", "/"), "topology.txt")
	else:
		return "./topology.txt"
