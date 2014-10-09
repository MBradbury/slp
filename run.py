#!/usr/bin/python

import os, struct

from protectionless.sim import GridSimulation

networkSize = 11
sourcePeriod = None
configuration = None
networkType = "GRID"

wirelessRange = 45

seed = struct.unpack("<i", os.urandom(4))[0]

with GridSimulation(seed, networkSize, wirelessRange) as sim:
	#print(dir(sim.tossim))

	sim.run()

	sim.metrics.printResults()
