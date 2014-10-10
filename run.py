#!/usr/bin/python

from __future__ import print_function

import os, struct

from simulator.Attacker import Attacker
from simulator.Builder import build
from simulator.Topology import *
from simulator.Configuration import *
from simulator.Simulation import Simulation

def secureRandom():
	return struct.unpack("<i", os.urandom(4))[0]

module = "template"

gui = False

network_size = 11
source_period = 1000
wirelessRange = 45.0

tfs_duration = 4000
fake_period = 500

configuration = CreateFurtherSinkCorner(network_size, wirelessRange - 2.5)

build(module,
	SOURCE_PERIOD_MS=source_period,
	SOURCE_NODE_ID=configuration.sourceId,
	SINK_NODE_ID=configuration.sinkId,
	TEMP_FAKE_DURATION_MS=tfs_duration,
	FAKE_PERIOD_MS=fake_period,
	ALGORITHM="GenericAlgorithm"
)

seed = secureRandom()

with Simulation(module, seed, configuration, wirelessRange, 30.0) as sim:

	sim.addAttacker(Attacker(sim, configuration.sourceId, configuration.sinkId))

	if gui:
		sim.setupGUI()

	sim.run()

	sim.metrics.printResults()
