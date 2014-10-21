#!/usr/bin/python

from __future__ import print_function

import sys, importlib

from simulator.Attacker import Attacker
from simulator.Builder import build
import simulator.Configuration as Configuration
from simulator.Simulation import Simulation

module = sys.argv[1]

Arguments = importlib.import_module("{}.Arguments".format(module))

a = Arguments.Arguments()
a.parse(sys.argv[2:])

configuration = Configuration.Create(a.args.configuration, a.args)

#print(configuration)
#print(configuration.topology.nodes)

with Simulation(module, configuration, a.args) as sim:

	sim.addAttacker(Attacker(sim, configuration.sourceId, configuration.sinkId))

	if a.args.mode == "GUI":
		sim.setupGUI()

	sim.run()

	sim.metrics.printResults()
