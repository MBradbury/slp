#!/usr/bin/python

from __future__ import print_function

import os, sys, struct, importlib

from simulator.Attacker import Attacker
from simulator.Builder import build
from simulator.Topology import *
from simulator.Configuration import *
from simulator.Simulation import Simulation

module = sys.argv[1]

Arguments = importlib.import_module("{}.Arguments".format(module))

a = Arguments.Arguments()
a.parse(sys.argv[2:])

configuration = CreateSourceCorner(a.args.network_size, a.args.wireless_range - 2.5)

with Simulation(module, configuration, a.args) as sim:

	sim.addAttacker(Attacker(sim, configuration.sourceId, configuration.sinkId))

	if a.args.mode == "GUI":
		sim.setupGUI()

	sim.run()

	sim.metrics.printResults()
