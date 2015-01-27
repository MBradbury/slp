#!/usr/bin/python

from __future__ import print_function

import sys, importlib, traceback

import simulator.Attacker as Attacker
from simulator.Builder import build
import simulator.Configuration as Configuration
from simulator.Simulation import Simulation

module = sys.argv[1]

Arguments = importlib.import_module("{}.Arguments".format(module))

a = Arguments.Arguments()
a.parse(sys.argv[2:])

configuration = Configuration.Create(a.args.configuration, a.args)

with Simulation(module, configuration, a.args) as sim:

    AttackerClass = getattr(Attacker, a.args.attacker_model)

    sim.add_attacker(AttackerClass(sim, configuration.source_id, configuration.sink_id))

    if a.args.mode == "GUI":
        sim.setup_gui()

    try:
        sim.run()
    except RuntimeError as e:
        print(e)
        print(traceback.format_exc())
    else:
        sim.metrics.print_results()
