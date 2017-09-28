from __future__ import print_function, division

import os.path

def parsers():
    return [
        ("SINGLE", None, ["verbose", "configuration", "attacker model", "fault model", "seed", "log file", "log converter"]),
        ("GUI", "SINGLE", ["gui scale"]),
    ]

def build(module, a):
    pass

def print_version():
    pass

def print_arguments(module, a):
    # Try to extract parameters from the log file name
    names = {name.rsplit("_", 1)[0] for name in a.args.log_file}

    if len(names) == 1:
        name = os.path.basename(next(iter(names)))

        (configuration, source_period, rf_power) = name.split("-")

        source_period = float(source_period.replace("_", "."))

        if configuration != a.args.configuration:
            raise RuntimeError("Configuration differs from the one specified")

        print("source_period=FixedPeriodModel(period={})".format(source_period))
        print("rf_power={}".format(rf_power))

    for (k, v) in sorted(vars(a.args).items()):
        if k not in a.arguments_to_hide:
            print("{}={}".format(k, v))

def run_simulation(module, a, count=1, print_warnings=False):
    import copy
    import sys

    import simulator.Configuration as Configuration
    import simulator.OfflineLogConverter as OfflineLogConverter

    configuration = Configuration.create(a.args.configuration, a.args)

    # Get the correct Simulation constructor
    if a.args.mode == "SINGLE":
        from simulator.Simulation import OfflineSimulation
    elif a.args.mode == "GUI":
        from simulator.TosVis import GuiOfflineSimulation as OfflineSimulation
    else:
        raise RuntimeError("Unknown mode {}".format(a.args.mode))

    for log_file in a.args.log_file:
        with OfflineLogConverter.create_specific(a.args.log_converter, log_file) as converted_event_log:
            with OfflineSimulation(module, configuration, a.args, event_log=converted_event_log) as sim:

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
