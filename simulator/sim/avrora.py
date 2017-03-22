from __future__ import print_function, division

import sys

try:
    import subprocess32 as subprocess
except ImportError:
    import subprocess

def parsers():
    raw_single_common = ["verbose", "seed", "configuration", "network size", "distance",
                         "node id order", "safety period",
                         "low powered listening",
                         "max buffer size"]

    return [
        ("SINGLE", None, raw_single_common + ["attacker model"]),
        ("RAW", None, raw_single_common + ["log file"]),
        ("GUI", "SINGLE", ["gui scale"]),
        #("PARALLEL", "SINGLE", ["job size", "thread count"]),
        #("CLUSTER", "PARALLEL", ["job id"]),
    ]

def build(module, a):
    import data.cycle_accurate
    from data.run.driver.cycle_accurate_builder import Runner as Builder

    from data import submodule_loader

    target = module.replace(".", "/") + ".txt"

    avrora = submodule_loader.load(data.cycle_accurate, "avrora")

    builder = Builder(avrora, max_buffer_size=a.args.max_buffer_size)
    builder.total_job_size = 1
    
    #(a, module, module_path, target_directory)
    builder.add_job((module, a), target)

def print_version():
    import simulator.VersionDetection as VersionDetection

    print("@version:tinyos={}".format(VersionDetection.tinyos_version()))
    print("@version:avrora={}".format(VersionDetection.avrora_version()))

    print("@version:java={}".format(VersionDetection.java_version()))

def avrora_command(module, a, configuration):
    from datetime import datetime
    import os

    try:
        avrora_path = os.environ["AVRORA_JAR_PATH"]
    except KeyError:
        raise RuntimeError("Unable to find the environment variable AVRORA_JAR_PATH so cannot run avrora.")

    target_directory = module.replace(".", "/")

    try:
        seconds_to_run = a.args.safety_period
    except AttributeError:
        slowest_source_period = a.args.source_period if isinstance(a.args.source_period, float) else a.args.source_period.slowest()
        seconds_to_run = configuration.size() * 4.0 * slowest_source_period

    # See: http://compilers.cs.ucla.edu/avrora/help/sensor-network.html
    options = {
        "platform": "micaz",
        "simulation": "sensor-network",
        "seconds": seconds_to_run,
        "monitors": "packet,c-print,energy",
        "radio-range": a.args.distance + 0.1,
        "nodecount": str(configuration.size()),
        "topology": "static",
        "topology-file": os.path.join(target_directory, "topology.txt"),
        "random-seed": a.args.seed,

        # Needed to be able to print simdbg strings longer than 30 bytes
        "max": a.args.max_buffer_size,

        # Show the messages sent and received
        "show-packets": "true",

        # Need to disable the simulator showing colors
        "colors": "false",

        # Report time in seconds and not cycles
        # Only need a precision of 6 as python cannot handle more than that
        "report-seconds": "true",
        "seconds-precision": "6"
    }

    target_file = os.path.join(target_directory, "main.elf")

    options_string = " ".join("-{}={}".format(k,v) for (k,v) in options.items())

    # Avrora is a bit crazy as it uses a one thread per node architecture
    # This is a problem when running on a cluster as we need a way to limit the number of cores being used.

    # For the time being we just use a niceness to prevent a system from freezing.

    # Give a niceness to allow system to continue to respond
    command = "nice -15 java -jar {} {} {}".format(avrora_path, options_string, target_file)

    print("@command:{}".format(command))

    return command

def avrora_iter(iterable):
    from datetime import datetime
    import re

    results_start = "------------------------------------------------------------------------------"
    results_end = "=============================================================================="

    RESULT_LINE_RE = re.compile(r'\s*(\d+)\s*(\d+:\d+:\d+\.\d+)\s*(.+)\s*')

    started = False
    ended = False

    for line in iterable:
        if not started:
            if line.startswith(results_start):
                started = True
            continue

        if line.startswith(results_end):
            ended = True
            return

        match = RESULT_LINE_RE.match(line)

        node = int(match.group(1))
        node_time = datetime.strptime(match.group(2)[:-3], "%H:%M:%S.%f")

        log = match.group(3)

        if log.startswith("---->") or log.startswith("<===="):
            pass
        else:
            stime_str = node_time.strftime("%Y/%m/%d %H:%M:%S.%f")

            full_str = stime_str + "|" + log

            #print(full_str)

            yield full_str

def run_simulation(module, a, count=1, print_warnings=False):
    import shlex

    from simulator import Configuration

    configuration = Configuration.create(a.args.configuration, a.args)

    command = shlex.split(avrora_command(module, a, configuration))

    if a.args.mode == "RAW":
        with open(a.args.log_file, "w") as out_file:
            subprocess.check_call(command, stdout=out_file)

    else:
        import copy

        if a.args.mode == "SINGLE":
            from simulator.Simulation import OfflineSimulation
        elif a.args.mode == "GUI":
            from simulator.TosVis import GuiOfflineSimulation as OfflineSimulation
        else:
            raise RuntimeError("Unknown mode {}".format(a.args.mode))

        with subprocess.Popen(command, stdout=subprocess.PIPE) as proc:
            proc_iter = iter(proc.stdout.readline, '')

            with OfflineSimulation(module, configuration, a.args, event_log=avrora_iter(proc_iter)) as sim:
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

                proc.wait()

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
