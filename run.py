#!/usr/bin/python

import os, struct

from simulator.Builder import build
from simulator.Topology import *
from simulator.Configuration import *
from protectionless.sim import Simulation

def secureRandom():
	return struct.unpack("<i", os.urandom(4))[0]


network_size = 11
source_period = None
configuration = None
networkType = "GRID"

wirelessRange = 45.0

grid = Grid(network_size, wirelessRange)

source_corner = Configuration(grid, sourceId=0, sinkId=(len(grid.nodes) - 1) / 2)



build("protectionless",
	SOURCE_PERIOD_MS=1000,
	SOURCE_NODE_ID=source_corner.sourceId,
	SINK_NODE_ID=source_corner.sinkId
)


seed = secureRandom()

with Simulation(seed, source_corner, wirelessRange) as sim:
	#print(dir(sim.tossim))

	sim.run()

	sim.metrics.printResults()
