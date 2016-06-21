#!/usr/bin/env python
from __future__ import print_function, division

import copy
import sys

import simulator.Configuration as Configuration

def run_simulation(module, a, count=1):
    
    configuration = Configuration.create(a.args.configuration, a.args)

    if a.args.mode == "GUI":
        from simulator.TosVis import GuiSimulation as Simulation
    else:
        from simulator.Simulation import Simulation

    for n in range(count):
        with Simulation(module, configuration, a.args) as sim:

            # Create a copy of the provided attacker model
            attacker = copy.deepcopy(a.args.attacker_model)

            # Setup each attacker model
            attacker.setup(sim, configuration.sink_id, 0)

            sim.add_attacker(attacker)

            try:
                sim.run()
            except Exception as ex:
                import traceback
                print("Killing run due to {}".format(ex), file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                return 1
            else:
                try:
                    sim.metrics.print_results()
                except Exception as ex:
                    import traceback
                    print("Failed to print metrics due to {}".format(ex), file=sys.stderr)
                    print(traceback.format_exc(), file=sys.stderr)
                    return 2

    return 0

if __name__ == "__main__":
    import importlib
    import math

    module = sys.argv[1]

    Arguments = importlib.import_module("{}.Arguments".format(module))

    a = Arguments.Arguments()
    a.parse(sys.argv[2:])

    result = run_simulation(module, a)

    sys.exit(result)
