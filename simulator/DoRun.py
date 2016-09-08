#!/usr/bin/env python
from __future__ import print_function, division

import copy
import functools
import sys

import simulator.Configuration as Configuration

def run_simulation(module, a, count=1):
    
    configuration = Configuration.create(a.args.configuration, a.args)

    # Get the correct Simulation constructor
    if a.args.mode == "GUI":
        from simulator.TosVis import GuiSimulation as Simulation

    elif a.args.mode == "OFFLINE":
        from simulator.Simulation import OfflineSimulation
        Simulation = functools.partial(OfflineSimulation, log_filename=a.args.merged_log)

    elif a.args.mode == "OFFLINE_GUI":
        from simulator.TosVis import GuiOfflineSimulation as OfflineSimulation
        Simulation = functools.partial(OfflineSimulation, log_filename=a.args.merged_log)

    else:
        from simulator.Simulation import Simulation

    for n in range(count):
        with Simulation(module, configuration, a.args) as sim:

            # Create a copy of the provided attacker model
            attacker = copy.deepcopy(a.args.attacker_model)

            # Setup each attacker model
            attacker.setup(sim, configuration.sink_id, ident=0)

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

                    all_args = "\n".join("{}={}".format(k, v) for (k, v) in vars(a.args).items() if k not in a.arguments_to_hide)

                    print("Failed to print metrics due to: {}".format(ex), file=sys.stderr)
                    print(traceback.format_exc(), file=sys.stderr)
                    print("For parameters:", file=sys.stderr)
                    print(all_args, file=sys.stderr)
                    return 2

    return 0

def main():
    import importlib

    module = sys.argv[1]

    Arguments = importlib.import_module("{}.Arguments".format(module))

    a = Arguments.Arguments()
    a.parse(sys.argv[2:])

    result = run_simulation(module, a)

    sys.exit(result)

if __name__ == "__main__":
    main()
