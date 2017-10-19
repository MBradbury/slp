#!/usr/bin/env python
from __future__ import print_function, division

import importlib
import os
import sys

import simulator.sim
import simulator.MetricsCommon as MetricsCommon
import simulator.VersionDetection as VersionDetection

from data import submodule_loader

def main(argv):

    if __debug__:
        if len(argv) <= 1:
            print("Please provide the algorithm module as the first parameter. (e.g., algorithm.protectionless)", file=sys.stderr)
            return 1

    module = argv[1]

    if __debug__:
        if not (module.startswith('algorithm.') or module.startswith('cluster.')):
            print("You can only run algorithms in the algorithm or cluster module.", file=sys.stderr)
            return 2

    Arguments = importlib.import_module("{}.Arguments".format(module))

    a = Arguments.Arguments()
    a.parse(argv[2:])

    sim = submodule_loader.load(simulator.sim, a.args.sim)

    if a.args.mode in ("SINGLE", "GUI", "RAW", "PARALLEL"):
        sim.build(module, a)

    # Make the mode SINGLE, as PROFILE is SINGLE except for not building the code
    if a.args.mode == "PROFILE":
        a.args.mode = "SINGLE"

    # Set the thread count, but only for jobs that need it
    if hasattr(a.args, "thread_count") and a.args.thread_count is None:
        import psutil
        # Set the number of usable CPUs
        a.args.thread_count = len(psutil.Process().cpu_affinity())

    # When doing cluster array jobs only print out this header information on the first job
    if a.args.mode != "CLUSTER" or a.args.job_id is None or a.args.job_id == 1:
        from datetime import datetime

        metrics_class = MetricsCommon.import_algorithm_metrics(module, a.args.sim)

        # Print out the versions of slp-algorithms-tinyos and tinyos being used
        print("@version:python={}".format(VersionDetection.python_version()))
        print("@version:numpy={}".format(VersionDetection.numpy_version()))

        print("@version:slp-algorithms={}".format(VersionDetection.slp_algorithms_version()))
        
        sim.print_version()

        # Print other potentially useful meta data
        print("@date:{}".format(str(datetime.now())))
        print("@host:{}".format(os.uname()))

        # Record what algorithm is being run and under what simulator
        print("@module:{}".format(module))
        print("@sim:{}".format(a.args.sim))

        # Print out the argument settings
        sim.print_arguments(module, a)

        # Print the header for the results
        metrics_class.print_header()

        # Make sure this header has been written
        sys.stdout.flush()

    # Because of the way TOSSIM is architectured each individual simulation
    # needs to be run in a separate process.
    if a.args.mode in ("GUI", "SINGLE", "RAW"):
        sim.run_simulation(module, a, print_warnings=True)
    else:
        _run_parallel(sim, module, a, argv)

def convert_parallel_args_to_single(argv, sim):
    new_args = list(argv[1:])

    # Specify that a single run should be performed
    new_args[2] = "SINGLE"

    # Remove any CLUSTER or PARALLEL parameters
    parsers = [
        "--" + x.replace(" ", "-")
        for (name, parent, opts)
        in sim.parsers()
        if name in ("CLUSTER", "PARALLEL")
        for x in opts
    ]

    indexes_to_delete = []

    for i, arg in enumerate(new_args):
        if arg in parsers:
            indexes_to_delete.append(i)
            indexes_to_delete.append(i+1)

    for i in sorted(indexes_to_delete, reverse=True):
        del new_args[i]

    return new_args

def _run_parallel(sim, module, a, argv):
    from datetime import datetime
    import multiprocessing.pool
    from threading import Lock
    import traceback

    try:
        import subprocess32 as subprocess
    except ImportError:
        import subprocess

    # Some simulators don't support running in parallel
    # only allow parallel instances for those that do
    if sim.supports_parallel():
        parallel_instances = a.args.thread_count
    else:
        parallel_instances = 1

    print_lock = Lock()

    def subprocess_args_with_seed_44(subprocess_args):
        subprocess_args = list(subprocess_args)

        try:
            seed_index = subprocess_args.index('--seed')
            subprocess_args[seed_index + 1] = '44'
        except ValueError:
            subprocess_args.append('--seed')
            subprocess_args.append('44')

        return subprocess_args


    def runner(args):
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            (stdoutdata, stderrdata) = process.communicate()

            # Multiple processes may be attempting to write out at the same
            # time, so this needs to be protected with a lock.
            #
            # Also the streams write method needs to be called directly,
            # as print has issues with newline printing and multithreading.
            with print_lock:
                sys.stdout.write(stdoutdata)
                sys.stdout.flush()

                sys.stderr.write(stderrdata)
                sys.stderr.flush()

            if process.returncode != 0:
                error_message = "Bad return code {} (with args: '{}')".format(process.returncode, args)

                # Negative return code indicates process terminated by signal
                # Do our best to add that information
                if process.returncode < 0:
                    try:
                        import signal
                        signals = {getattr(signal, n): n for n in dir(signal) if n.startswith("SIG") and not n.startswith("SIG_")}
                        signal_name = signals.get(-process.returncode, None)
                        if signal_name:
                            error_message += ". Process killed by signal {}({})".format(signal_name, -process.returncode)
                    except:
                        # Ignore any exceptions that occur, we are just trying to help the users
                        pass

                with print_lock:
                    print(error_message, file=sys.stderr)
                    sys.stderr.flush()
                raise RuntimeError(error_message)

        except (KeyboardInterrupt, SystemExit) as ex:
            with print_lock:
                print("Killing process due to {}".format(ex), file=sys.stderr)
                sys.stdout.flush()
                sys.stderr.flush()
            process.kill()
            raise

    new_args = convert_parallel_args_to_single(argv, sim)

    subprocess_args = ["python", "-OO", "-m", "simulator.DoRun"] + new_args
    subprocess_args_44 = subprocess_args_with_seed_44(subprocess_args)

    if a.args.mode == "CLUSTER":
        if a.args.job_id is not None:
            print("Starting cluster array job id {} at {}".format(a.args.job_id, datetime.now()), file=sys.stderr)
        else:
            print("Starting cluster job at {}".format(datetime.now()), file=sys.stderr)
    elif a.args.mode == "PARALLEL":
        print("Starting parallel job at {}".format(datetime.now()), file=sys.stderr)
    else:
        raise RuntimeError("Unknown job type of {}".format(a.args.mode))

    print("Creating a process pool with {} processes.".format(parallel_instances), file=sys.stderr)

    sys.stderr.flush()

    # Use a thread pool for a number of reasons:
    # 1. We don't need the GIL-free nature of a process pool as our work is done in subprocesses
    # 2. If this process hangs the threads will terminate when this process is killed.
    #    The process pool would stay alive.
    job_pool = multiprocessing.pool.ThreadPool(processes=parallel_instances)

    # Always run with a seed of 44 first and second.
    # This allows us to do compatibility checks.
    # It also allows us to test the determinism of this set of parameters.
    all_args = [subprocess_args_44, subprocess_args_44] + [subprocess_args] * a.args.job_size

    try:
        result = job_pool.map_async(runner, all_args)

        # No more jobs to submit
        job_pool.close()

        # Use get so any exceptions are rethrown
        result.get()

        if not result.successful():
            print("The map_async was not successful", file=sys.stderr)

    except (KeyboardInterrupt, SystemExit) as ex:
        print("Killing thread pool due to {} at {}".format(ex, datetime.now()), file=sys.stderr)
        job_pool.terminate()
        raise
    except Exception as ex:
        print("Encountered: {} at {}".format(ex, datetime.now()), file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        job_pool.terminate()
        raise
    finally:
        job_pool.join()

        if a.args.mode == "CLUSTER":
            if a.args.job_id is not None:
                print("Finished cluster array job id {} at {}".format(a.args.job_id, datetime.now()), file=sys.stderr)
            else:
                print("Finished cluster job at {}".format(datetime.now()), file=sys.stderr)
        elif a.args.mode == "PARALLEL":
            print("Finished parallel job at {}".format(datetime.now()), file=sys.stderr)
        else:
            raise RuntimeError("Unknown job type of {}".format(a.args.mode))

        sys.stdout.flush()
        sys.stderr.flush()

    return 0

if __name__ == "__main__":
    result = main(sys.argv)
    sys.exit(result)
