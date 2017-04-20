from __future__ import print_function, division

def parsers():
    return [
        ("SINGLE", None, ["verbose", "seed", "configuration", "network size", "distance",
                          "node id order", "safety period",
                          "communication model", "noise model", "attacker model", "fault model",
                          "start time"]),
        ("PROFILE", "SINGLE", []),
        #("RAW", "SINGLE", ["log file"]),
        ("GUI", "SINGLE", ["gui scale", "gui node label"]),
        ("PARALLEL", "SINGLE", ["job size", "thread count"]),
        ("CLUSTER", "PARALLEL", ["job id"]),
    ]

# TOSSIM can be run in parallel as it only uses a single thread
def supports_parallel():
    return True

def build(module, a):
    import os.path

    import simulator.Builder as Builder
    import simulator.Configuration as Configuration

    # Only check dependencies on non-cluster runs
    # Cluster runs will have the dependencies checked in create.py
    from simulator import dependency
    dependency.check_all()

    configuration = Configuration.create(a.args.configuration, a.args)

    build_arguments = a.build_arguments()

    build_arguments.update(configuration.build_arguments())

    # Now build the simulation with the specified arguments
    Builder.build_sim(module.replace(".", os.path.sep), **build_arguments)

def print_version():
    import simulator.VersionDetection as VersionDetection

    print("@version:tinyos={}".format(VersionDetection.tinyos_version()))

def run_simulation(module, a, count=1, print_warnings=False):
    import copy
    import sys

    import simulator.Configuration as Configuration
    
    configuration = Configuration.create(a.args.configuration, a.args)

    # Get the correct Simulation constructor
    if a.args.mode == "SINGLE":
        from simulator.Simulation import Simulation
    elif a.args.mode == "GUI":
        from simulator.TosVis import GuiSimulation as Simulation
    else:
        raise RuntimeError("Unknown mode {}".format(a.args.mode))

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
