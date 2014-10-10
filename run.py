#!/usr/bin/python

import os, struct

from simulator.Builder import build
from simulator.Topology import *
from simulator.Configuration import *
from template.sim import Simulation

def secureRandom():
	return struct.unpack("<i", os.urandom(4))[0]


network_size = 11
source_period = 1000
wirelessRange = 45.0

tfs_duration = 4000
fake_period = 500

grid = Grid(network_size, wirelessRange - 2.5)

source_corner = Configuration(grid, sourceId=0, sinkId=(len(grid.nodes) - 1) / 2)

print(source_corner.topology.nodes)

build("template",
	SOURCE_PERIOD_MS=source_period,
	SOURCE_NODE_ID=source_corner.sourceId,
	SINK_NODE_ID=source_corner.sinkId,
	TEMP_FAKE_DURATION_MS=tfs_duration,
	FAKE_PERIOD_MS=fake_period,
	ALGORITHM="GenericAlgorithm"
)


seed = secureRandom()

with Simulation(seed, source_corner, wirelessRange, 30.0) as sim:
	#print(dir(sim.tossim))

	sim.run()

	sim.metrics.printResults()

