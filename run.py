#!/usr/bin/env python
from __future__ import print_function

import importlib
import sys

module = sys.argv[1]

Arguments = importlib.import_module("{}.Arguments".format(module))

a = Arguments.Arguments()
a.parse(sys.argv[2:])

# For cluster runs, the binary has already been built and the
# topology file has been written. So do not attempt to do so again.
#
# Also do not build for offline analysis runs
if a.args.mode not in {"CLUSTER", "OFFLINE", "OFFLINE_GUI"}:
    import os.path

    import simulator.Builder as Builder
    from simulator.Simulation import Simulation
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

# Set the thread count, but only for jobs that need it
if a.args.mode in {"CLUSTER", "PARALLEL"}:
    if a.args.thread_count is None:
        import multiprocessing
        a.args.thread_count = multiprocessing.cpu_count()

# When doing cluster array jobs only print out this header information on the first job
if a.args.mode != "CLUSTER" or a.args.job_id is None or a.args.job_id == 1:

    Metrics = importlib.import_module("{}.Metrics".format(module))

    # Print out the argument settings
    for (k, v) in vars(a.args).items():
        if k not in a.arguments_to_hide:
            print("{}={}".format(k, v))

    # Print the header for the results
    Metrics.Metrics.print_header()

    # Make sure this header has been written
    sys.stdout.flush()

# Because of the way TOSSIM is architectured each individual simulation
# needs to be run in a separate process.
if a.args.mode in {"GUI", "SINGLE", "OFFLINE", "OFFLINE_GUI"}:
    from simulator.DoRun import run_simulation
    run_simulation(module, a)

else:
    from datetime import datetime
    import multiprocessing.pool
    import subprocess
    from threading import Lock
    import traceback

    print_lock = Lock()

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
                error_message = "Bad return code {}".format(process.returncode)
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

    subprocess_args = ["python", "-OO", "-m", "simulator.DoRun"] + sys.argv[1:]

    if a.args.job_id is not None:
        print("Starting cluster array job id {} at {}".format(a.args.job_id, datetime.now()), file=sys.stderr)
    else:
        print("Starting cluster job at {}".format(datetime.now()), file=sys.stderr)

    print("Creating a process pool with {} processes.".format(a.args.thread_count), file=sys.stderr)

    sys.stderr.flush()

    # Use a thread pool for a number of reasons:
    # 1. We don't need the GIL-free nature of a process pool as our work is done is subprocesses
    # 2. If this process hangs the threads will terminate when this process is killed.
    #    The process pool would stay alive.
    job_pool = multiprocessing.pool.ThreadPool(processes=a.args.thread_count)

    try:
        result = job_pool.map_async(runner, [subprocess_args] * a.args.job_size)

        # No more jobs to submit
        job_pool.close()

        # Use get so any exceptions are rethrown
        result.get()

        if not result.successful():
            print("The map_async was not successful", file=sys.stderr)

    except (KeyboardInterrupt, SystemExit) as ex:
        print("Killing thread pool due to {}".format(ex), file=sys.stderr)
        job_pool.terminate()
        raise
    except Exception as ex:
        print("Encountered: {}".format(ex), file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        job_pool.terminate()
        raise
    finally:
        job_pool.join()

        if a.args.job_id is not None:
            print("Finished cluster array job id {} at {}".format(a.args.job_id, datetime.now()), file=sys.stderr)
        else:
            print("Finished cluster job at {}".format(datetime.now()), file=sys.stderr)

        sys.stderr.flush()
