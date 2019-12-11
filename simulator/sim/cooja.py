from __future__ import print_function, division

generate_per_node_id_binary = False

cluster_need_java = True

def parsers():
    # WARNING!!
    # Cooja cannot support a "node id order" of randomised until there is a way for a node
    # to find out its topology id during simulation.
    # Allowing randomised will break the ability to build one binary and use
    # it with different random seeds

    raw_single_common = ["verbose", "low verbose", "debug", "seed", "configuration", "network size", "distance",
                         "fault model", "node id order", "safety period", "start time",
                         "low power listening", "cooja", "cc2420", "extra metrics", "show raw log"]

    return [
        ("SINGLE", None, raw_single_common + ["attacker model"]),
        ("RAW", None, raw_single_common),
        ("PROFILE", "SINGLE", ["cooja profile"]),
        ("GUI", "SINGLE", ["gui scale"]),
        ("PARALLEL", "SINGLE", ["job size"]),
        ("CLUSTER", "PARALLEL", ["job id"]),
    ]

global_parameter_names = ('network size', 'configuration',
                          'attacker model', 'radio model',
                          'fault model',
                          'distance', 'node id order',
                          'latest node start time', 'platform',
                          'low power listening',
                          'source period')

def supports_parallel():
    # COOJA cannot be run in parallel as it uses a thread per node
    return False

def build(module, a):
    import data.cycle_accurate
    from data.run.driver.cooja_builder import Runner as Builder

    from data import submodule_loader

    target = module.replace(".", "/") + ".txt"

    cooja = submodule_loader.load(data.cycle_accurate, "cooja")

    builder = Builder(cooja, max_buffer_size=a.args.max_buffer_size, platform=a.args.platform.platform(), quiet=True)
    builder.total_job_size = 1
    
    #(a, module, module_path, target_directory)
    builder.add_job((module, a), target)

    # 0 For successful build result
    return 0

def print_version():
    import simulator.VersionDetection as VersionDetection

    print("@version:tinyos={}".format(VersionDetection.tinyos_version()))
    print("@version:contiki={}".format(VersionDetection.contiki_version()))

    print("@version:java={}".format(VersionDetection.java_version()))

def cooja_command(module, a, configuration):
    import os

    try:
        cooja_path = os.path.join(os.environ["CONTIKI_DIR"], "tools", "cooja", "dist", "cooja.jar")
    except KeyError:
        raise RuntimeError("Unable to find the environment variable CONTIKI_DIR so cannot run cooja.")

    target_directory = module.replace(".", "/")

    csc_file = os.path.join(target_directory, f"sim.{a.args.seed}.csc")

    profile = ""
    cooja_profile = getattr(a.args, "cooja_profile", None)
    if cooja_profile:
        if cooja_profile == "hprof":
            profile = "-agentlib:hprof=file=hprof.txt,cpu=samples,thread=y,depth=10"
        elif cooja_profile == "async-profiler":
            async_profiler_path = os.path.join(os.environ["ASYNC_PROFILER_PATH"], "libasyncProfiler.so")
            profile = f"-agentpath:{async_profiler_path}=start,o=summary,flat=200,file=out.txt,t"
        else:
            raise RuntimeError(f"Unknown COOJA profiler {cooja_profile}")

    # Enable assertions if in debug mode
    debug = "-ea" if a.args.debug else ""

    command = f"java {debug} {profile} -jar '{cooja_path}' -nogui='{csc_file}' -contiki='{os.environ['CONTIKI_DIR']}'"

    return command


def cooja_iter(iterable):
    from datetime import datetime

    exception = None

    for line in iterable:
        line = line.rstrip()

        # Skip empty lines
        if not line:
            continue

        if exception is not None:
            exception += "\n" + line
            continue

        if line.startswith('Exception') :
            exception = line
            continue

        try:
            time_us, rest = line.split("|", 1)
        except:
            print(f"Failed to process {line}")
            raise

        time_s = float(time_us) / 1000000.0

        node_time = datetime.fromtimestamp(time_s)

        stime_str = node_time.strftime("%Y/%m/%d %H:%M:%S.%f")

        # When running in cooja log output mode, an extra "DEBUG: " gets prepended
        # remove this here.
        if rest.startswith("DEBUG: "):
            rest = rest[len("DEBUG: "):]

        yield stime_str + "|" + rest

    if exception is not None:
        raise RuntimeError(f"Cooja exception: '{exception}'")

def print_arguments(module, a):
    for (k, v) in sorted(vars(a.args).items()):
        if k not in a.arguments_to_hide:
            print("{}={}".format(k, v))

def run_simulation(module, a, count=1, print_warnings=False):
    import shlex
    import sys
    import subprocess

    from simulator import Configuration

    from data.cycle_accurate.cooja import write_csc

    if a.args.node_id_order != "topology":
        raise RuntimeError("COOJA does not support a nido other than topology")

    configuration = Configuration.create(a.args.configuration, a.args)

    command = cooja_command(module, a, configuration)

    if a.args.mode == "GUI":
        print(f"@command:{command}")
        sys.stdout.flush()

    command = shlex.split(command)    

    if a.args.mode == "RAW":
        if count != 1:
            raise RuntimeError("Cannot run cooja multiple times in RAW mode")

        write_csc(module.replace(".", "/"), a)

        with subprocess.Popen(command, stderr=subprocess.PIPE, universal_newlines=True) as proc:

            proc_iter = iter(proc.stderr.readline, '')

            for line in cooja_iter(proc_iter):
                print(line)

            proc.stderr.close()

            try:
                return_code = proc.wait(timeout=1)

                if return_code:
                    raise subprocess.CalledProcessError(return_code, command)

            except subprocess.TimeoutExpired:
                print("Timeout expired, killing Cooja proc")
                proc.terminate()

    else:
        if a.args.mode == "SINGLE":
            from simulator.Simulation import OfflineSimulation
        elif a.args.mode == "GUI":
            from simulator.TosVis import GuiOfflineSimulation as OfflineSimulation
        else:
            raise RuntimeError(f"Unknown mode {a.args.mode}")

        for n in range(count):

            write_csc(module.replace(".", "/"), a)

            with subprocess.Popen(command, stdout=sys.stderr, stderr=subprocess.PIPE, universal_newlines=True) as proc:

                proc_iter = iter(proc.stderr.readline, '')

                with OfflineSimulation(module, configuration, a.args, event_log=cooja_iter(proc_iter)) as sim:
                    
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

                        proc.kill()

                        return 51

                    proc.stderr.close()

                    try:
                        return_code = proc.wait(timeout=1)
                        if return_code:
                            raise subprocess.CalledProcessError(return_code, command)

                    except subprocess.TimeoutExpired:
                        proc.terminate()

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

                        proc.kill()
                        
                        return 52

    return 0
