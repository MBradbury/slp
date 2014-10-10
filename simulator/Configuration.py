
import math

from simulator.Topology import *

class Configuration:
	def __init__(self, topology, sourceId, sinkId, spaceBehindSink):
		self.topology = topology
		self.sinkId = sinkId
		self.sourceId = sourceId
		self.spaceBehindSink = spaceBehindSink

		if self.sinkId >= len(self.topology.nodes):
			raise Exception("There are not enough nodes ({}) to have a sink id of {}".format(len(self.topology.nodes), self.sinkId))

		if self.sourceId >= len(self.topology.nodes):
			raise Exception("There are not enough nodes ({}) to have a source id of {}".format(len(self.topology.nodes), self.source))

def CreateSourceCorner(size, distance):
	grid = Grid(size, distance)

	return Configuration(grid,
		sourceId=0,
		sinkId=(len(grid.nodes) - 1) / 2,
		spaceBehindSink=True)

def CreateSinkCorner(size, distance):
	grid = Grid(size, distance)

	return Configuration(grid,
		sourceId=(len(grid.nodes) - 1) / 2,
		sinkId=len(grid.nodes) - 1,
		spaceBehindSink=False)

def CreateFurtherSinkCorner(size, distance):
	grid = Grid(size, distance)

	return Configuration(grid,
		sourceId=(size + 1) * 3,
		sinkId=len(grid.nodes) - 1,
		spaceBehindSink=False)
