
from scipy.spatial.distance import euclidean

class Grid:
	def __init__(self, size, distance, initialPosition=100):
		self.size = size

		self.nodes = [(float(x * distance + initialPosition), float(y * distance + initialPosition))
			for y in xrange(size)
			for x in xrange(size)]

		self.centreNode = self.nodes[(len(self.nodes) - 1) / 2]

class Circle:
	def __init__(self, diameter, distance, initialPosition=100):
		self.diameterInHops = diameter
		self.diameter = self.diameterInHops * distance

		self.nodes = [(float(x * distance + initialPosition), float(y * distance + initialPosition))
			for y in xrange(diameter)
			for x in xrange(diameter)]

		self.centreNode = (len(self.nodes) - 1) / 2

		centreNodePos = self.nodes[self.centreNode]

		def isInCircle(position):
			return euclidean(centreNodePos, position) < self.diameter / 2.0

		#print([euclidean(centreNodePos, position) for position in self.nodes])

		self.nodes = [pos for pos in self.nodes if isInCircle(pos)]

class Ring:
	def __init__(self, diameter, distance, initialPosition=100):
		self.diameter = diameter

		self.nodes = [(float(x * distance + initialPosition), float(y * distance + initialPosition))
			for y in xrange(diameter)
			for x in xrange(diameter)
			if (x == 0 or x == diameter -1) or (y == 0 or y == diameter - 1)]
