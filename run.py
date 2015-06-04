#!/usr/bin/python

from __future__ import print_function

import sys, importlib

module = sys.argv[1]

Arguments = importlib.import_module("{}.Arguments".format(module))
Metrics = importlib.import_module("{}.Metrics".format(module))

a = Arguments.Arguments()
a.parse(sys.argv[2:])

# For cluster runs, the binary has already been built and the
# topology file has been written. So do not attempt to do so again.
if a.args.mode != "CLUSTER":
    import simulator.Builder as Builder
    from simulator.Simulation import Simulation
    import simulator.Configuration as Configuration

    configuration = Configuration.create(a.args.configuration, a.args)

    build_arguments = a.build_arguments()

    build_arguments.update(configuration.build_arguments())

    # Now build the simulation with the specified arguments
    Builder.build(module.replace(".", "/"), **build_arguments)

    # Need to build the topology.txt file once.
    # Do it now as if done later it will be created
    # once per process and could potentially race with other processes
    # that need to create this file.
    #
    # The assumption is that any processes running are of the same topology
    Simulation.write_topology_file(configuration.topology.nodes)

for (k, v) in vars(a.args).items():
    print("{}={}".format(k, v))

Metrics.Metrics.print_header()

# Because of the way TOSSIM is architectured each individual simulation
# needs to be run in a separate process.
if a.args.mode == "GUI":
    import simulator.DoRun

else:
    import subprocess, multiprocessing.pool, traceback
    from threading import Lock

    print_lock = Lock()

    def runner(args):
        def runner_impl(args):
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                process.wait()

                # Multiple processes may be attempting to write out at the same
                # time, so this needs to be protected with a lock.
                #
                # Also the streams write method needs to be called directly,
                # as print has issues with newline printing and multithreading.
                with print_lock:
                    for line in process.stdout:
                        sys.stdout.write(line)
                    sys.stdout.flush()

                    for line in process.stderr:
                        sys.stderr.write(line)
                    sys.stderr.flush()

                if process.returncode != 0:
                    with print_lock:
                        print("Bad return code {}".format(process.returncode), file=sys.stderr)
                    raise RuntimeError("Bad return code {}".format(process.returncode))

            except (KeyboardInterrupt, SystemExit) as e:
                with print_lock:
                    print("Killing process due to {}".format(e), file=sys.stderr)
                process.terminate()
                raise

        max_retries = 3
        tries = 0
        done = False

        while not done and tries < max_retries:
            try:
                tries += 1
                runner_impl(args)
                done = True
            except Exception as e:
                with print_lock:
                    print("Encountered (try {}): {}".format(tries, e), file=sys.stderr)
                    print(traceback.format_exc(), file=sys.stderr)

    subprocess_args = ["python", "-m", "simulator.DoRun"] + sys.argv[1:]

    print("Creating a process pool with {} processes.".format(a.args.thread_count), file=sys.stderr)

    p = multiprocessing.pool.ThreadPool(processes=a.args.thread_count)
    try:
        r = p.map_async(runner, [subprocess_args] * a.args.job_size)

        # Use get so any exceptions are rethrown
        r.get()

        if not r.successful():
            print("The map_async was not successful", file=sys.stderr)

    except (KeyboardInterrupt, SystemExit) as e:
        print("Killing thread pool due to {}".format(e), file=sys.stderr)
    except Exception as e:
        print("Encountered: {}".format(e), file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
    finally:
        p.terminate()
        p.join()
