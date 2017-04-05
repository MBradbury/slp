from __future__ import print_function, division

def parsers():
    return [
        ("SINGLE", None, ["verbose", "configuration", "log file"]),
        ("GUI", "SINGLE", ["gui scale"]),
    ]

def build(module, a):
    pass

def print_version():
    pass

def run_simulation(module, a, count=1, print_warnings=False):
    import copy

    import simulator.Configuration as Configuration

    configuration = Configuration.create(a.args.configuration, a.args)

    # Get the correct Simulation constructor
    if a.args.mode == "SINGLE":
        from simulator.Simulation import OfflineSimulation
    elif a.args.mode == "GUI":
        from simulator.TosVis import GuiOfflineSimulation as OfflineSimulation
    else:
        raise RuntimeError("Unknown mode {}".format(a.args.mode))

    with open(a.args.log_file, "r") as log_file:
        with OfflineSimulation(module, configuration, a.args, even_log=log_file) as sim:

            # Create a copy of the provided attacker model
            attacker = copy.deepcopy(a.args.attacker_model)

            # Setup each attacker model
            attacker.setup(sim, configuration.sink_id, ident=0)

            sim.add_attacker(attacker)

            try:
                sim.run()
            except Exception as ex:
                import traceback
                
                all_args = "\n".join("{}={}".format(k, v) for (k, v) in vars(a.args).items() if k not in a.arguments_to_hide)

                print("Killing run due to {}".format(ex), file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                print("For parameters:", file=sys.stderr)
                print(all_args, file=sys.stderr)

                return 51

            try:
                sim.metrics.print_results()
            except Exception as ex:
                import traceback

                all_args = "\n".join("{}={}".format(k, v) for (k, v) in vars(a.args).items() if k not in a.arguments_to_hide)

                print("Failed to print metrics due to: {}".format(ex), file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                print("For parameters:", file=sys.stderr)
                print(all_args, file=sys.stderr)
                
                return 52

            if print_warnings:
                sim.metrics.print_warnings()

    return 0
