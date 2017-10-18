from __future__ import print_function, division

import sys
import os.path
import importlib

def parsers():
    return [
        ("SINGLE", None, ["verbose", "configuration", "attacker model", "fault model", "safety period",
                          "seed", "log file", "log converter", "nonstrict"]),
        ("GUI", "SINGLE", ["gui scale"]),
    ]

def build(module, a):
    pass

def print_version():
    pass

def print_arguments(module_name, a):
    # Try to extract parameters from the log file name
    names = {name.rsplit("_", 1)[0] for name in a.args.log_file}

    if len(names) == 1:
        name = os.path.basename(next(iter(names)))

        params = list(name.split("-"))

        module = importlib.import_module(module_name)
        local_parameter_names = module.local_parameter_names

        # Some testbeds need short names, so the default fault model may be omitted
        if len(params) == 4 + len(local_parameter_names):
            (configuration, fault_model, source_period) = params[:3]
            del params[:3]

        elif len(params) == 3 + len(local_parameter_names):
            (configuration, source_period) = params[:2]
            del params[:2]

            fault_model = "ReliableFaultModel()"

        else:
            raise RuntimeError("Don't know how to work out what these parameters are")

        if configuration != a.args.configuration:
            raise RuntimeError("Configuration ({}) differs from the one specified ({})".format(configuration, a.args.configuration))

        if fault_model != str(a.args.fault_model):
            raise RuntimeError("FaultModel ({}) differs from the one specified ({})".format(fault_model, a.args.fault_model))

        # Last Parameter is always rf power
        rf_power = params.pop(-1)

        local_parameter_values = zip(local_parameter_names, params)

        source_period = float(source_period.replace("_", "."))
        print("source_period=FixedPeriodModel(period={})".format(source_period))

        for (name, value) in local_parameter_values:
            print("{}={}".format(name.replace(" ", "_"), value.replace("_", ".")))

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
        if a.args.verbose:
            print("Analysing log file {}".format(log_file), file=sys.stderr)
        with OfflineLogConverter.create_specific(a.args.log_converter, log_file) as converted_event_log:
            with OfflineSimulation(module, configuration, a.args, event_log=converted_event_log) as sim:

                # Create a copy of the provided attacker model
                attacker = copy.deepcopy(a.args.attacker_model)

                if len(configuration.sink_ids) != 1:
                    raise RuntimeError("Attacker does not know where to start!")

                attacker_start = next(iter(configuration.sink_ids))

                # Setup each attacker model
                attacker.setup(sim, attacker_start, ident=0)

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
                    print("In file: {}".format(log_file), file=sys.stderr)

                    return 51

                try:
                    sim.metrics.print_results()

                    if print_warnings:
                        sim.metrics.print_warnings()

                except Exception as ex:
                    import traceback

                    all_args = "\n".join("{}={}".format(k, v) for (k, v) in vars(a.args).items() if k not in a.arguments_to_hide)

                    print("Failed to print metrics due to: {}".format(ex), file=sys.stderr)
                    print(traceback.format_exc(), file=sys.stderr)
                    print("For parameters:", file=sys.stderr)
                    print(all_args, file=sys.stderr)
                    print("In file: {}".format(log_file), file=sys.stderr)
                    
                    return 52

    return 0
