
import os, struct

from protectionless.sim import GridSimulation

networkSize = 11
sourcePeriod = None
configuration = None
networkType = "GRID"

wirelessRange = 45

seed = struct.unpack("<i", os.urandom(4))[0]

sim = GridSimulation(seed, networkSize, wirelessRange)

sim.run()

sim.metrics.printResults()
