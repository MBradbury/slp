#!/usr/bin/env python
from __future__ import print_function, division

import importlib
import os
import sys

import simulator.VersionDetection as VersionDetection

def main(argv):
    module = argv[1]

    Arguments = importlib.import_module("{}.Arguments".format(module))

    a = Arguments.Arguments()
    a.parse(argv[2:])

    if a.args.mode == "CYCLEACCURATE":
        from simulator.DoCycleAccurateRun import main as main_cycle_accurate
        main_cycle_accurate(module, a)
        sys.exit(0)

    # For cluster runs, the binary has already been built and the
    # topology file has been written. So do not attempt to do so again.
    #
    # Also do not build for offline analysis runs
    if a.args.mode not in ("PROFILE", "CLUSTER", "OFFLINE", "OFFLINE_GUI"):
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

    # Make the mode SINGLE, as PROFILE is SINGLE except for not building the code
    if a.args.mode == "PROFILE":
        a.args.mode = "SINGLE"

    # Set the thread count, but only for jobs that need it
    if a.args.mode in ("CLUSTER", "PARALLEL"):
        if a.args.thread_count is None:
            import multiprocessing
            a.args.thread_count = multiprocessing.cpu_count()

    # When doing cluster array jobs only print out this header information on the first job
    if a.args.mode != "CLUSTER" or a.args.job_id is None or a.args.job_id == 1:
        from datetime import datetime

        Metrics = importlib.import_module("{}.Metrics".format(module))

        # Print out the versions of slp-algorithms-tinyos and tinyos being used
        print("@version:python={}".format(VersionDetection.python_version()))
        print("@version:numpy={}".format(VersionDetection.numpy_version()))

        print("@version:slp-algorithms={}".format(VersionDetection.slp_algorithms_version()))
        print("@version:tinyos={}".format(VersionDetection.tinyos_version()))

        # Print other potentially useful meta data
        print("@date:{}".format(str(datetime.now())))
        print("@host:{}".format(os.uname()))

        # Record what algorithm is being run
        print("@module:{}".format(module))

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
    if a.args.mode in ("GUI", "SINGLE", "OFFLINE", "OFFLINE_GUI"):
        from simulator.DoRun import run_simulation
        run_simulation(module, a, print_warnings=True)

    else:
        from datetime import datetime
        import multiprocessing.pool
        from threading import Lock
        import traceback

        try:
            import subprocess32 as subprocess
        except ImportError:
            import subprocess

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

        subprocess_args = ["python", "-OO", "-m", "simulator.DoRun"] + argv[1:]
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

        print("Creating a process pool with {} processes.".format(a.args.thread_count), file=sys.stderr)

        sys.stderr.flush()

        # Use a thread pool for a number of reasons:
        # 1. We don't need the GIL-free nature of a process pool as our work is done is subprocesses
        # 2. If this process hangs the threads will terminate when this process is killed.
        #    The process pool would stay alive.
        job_pool = multiprocessing.pool.ThreadPool(processes=a.args.thread_count)

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

if __name__ == "__main__":
    main(sys.argv)
