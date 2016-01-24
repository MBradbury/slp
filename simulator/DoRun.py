#!/usr/bin/env python
from __future__ import print_function

import sys, importlib, traceback, copy

import simulator.Configuration as Configuration
from simulator.Simulation import Simulation

module = sys.argv[1]

Arguments = importlib.import_module("{}.Arguments".format(module))

a = Arguments.Arguments()
a.parse(sys.argv[2:])

configuration = Configuration.create(a.args.configuration, a.args)

with Simulation(module, configuration, a.args) as sim:

    # Create a copy of the provided attacker model
    attacker = copy.deepcopy(a.args.attacker_model)

    # Setup each attacker model
    attacker.setup(sim, configuration.sink_id)

    sim.add_attacker(attacker)

    if a.args.mode == "GUI":
        sim.setup_gui()

    try:
        sim.run()
    except (KeyboardInterrupt, SystemExit, RuntimeError) as ex:
        print("Killing run due to {}".format(ex), file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(3)
    else:
        sim.metrics.print_results()

sys.exit(0)
