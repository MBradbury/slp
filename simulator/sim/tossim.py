from __future__ import print_function, division

cluster_need_java = False

def parsers():
    return [
        ("SINGLE", None, ["verbose", "debug", "seed", "configuration", "network size", "distance",
                          "node id order", "safety period",
                          "communication model", "noise model", "attacker model", "fault model",
                          "start time", "extra metrics"]),
        ("PROFILE", "SINGLE", []),
        #("RAW", "SINGLE", ["log file"]),
        ("GUI", "SINGLE", ["gui scale", "gui node label"]),
        ("PARALLEL", "SINGLE", ["job size", "thread count"]),
        ("CLUSTER", "PARALLEL", ["job id"]),
    ]

global_parameter_names = ('network size', 'configuration',
                          'attacker model', 'noise model',
                          'communication model', 'fault model',
                          'distance', 'node id order',
                          'latest node start time',
                          'source period')

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
    return Builder.build_sim(module.replace(".", os.path.sep), **build_arguments)

def print_version():
    import simulator.VersionDetection as VersionDetection

    print("@version:tinyos={}".format(VersionDetection.tinyos_version()))

def print_arguments(module, a):
    for (k, v) in sorted(vars(a.args).items()):
        if k not in a.arguments_to_hide:
            print("{}={}".format(k, v))

def run_simulation(module, a, count=1, print_warnings=False):
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

            a.args.attacker_model.setup(sim)

            try:
                sim.run()
            except Exception as ex:
                import traceback
                
                all_args = "\n".join(f"{k}={v}" for (k, v) in vars(a.args).items())

                print("Killing run due to {}".format(ex), file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                print("For parameters:", file=sys.stderr)
                print("With seed:", sim.seed, file=sys.stderr)
                print(all_args, file=sys.stderr)

                return 51

            try:
                sim.metrics.print_results()

                if print_warnings:
                    sim.metrics.print_warnings()

            except Exception as ex:
                import traceback

                all_args = "\n".join(f"{k}={v}" for (k, v) in vars(a.args).items())

                print("Failed to print metrics due to: {}".format(ex), file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                print("For parameters:", file=sys.stderr)
                print("With seed:", sim.seed, file=sys.stderr)
                print(all_args, file=sys.stderr)
                
                return 52

    return 0
