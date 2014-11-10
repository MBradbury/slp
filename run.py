#!/usr/bin/python

from __future__ import print_function

import sys, importlib, subprocess, multiprocessing, traceback

from threading import Lock

from simulator.Attacker import Attacker
from simulator.Builder import build
import simulator.Configuration as Configuration
from simulator.Simulation import Simulation

module = sys.argv[1]

Arguments = importlib.import_module("{}.Arguments".format(module))
Metrics = importlib.import_module("{}.Metrics".format(module))

a = Arguments.Arguments()
a.parse(sys.argv[2:])

configuration = Configuration.Create(a.args.configuration, a.args)

# For cluster runs, the binary has already been built and the
# topology file has been written. So do not attempt to do so again.
if a.args.mode != "CLUSTER":
	build_arguments = a.getBuildArguments()

	build_arguments.update(configuration.getBuildArguments())

	# Now build the simulation with the specified arguments
	build(module, **build_arguments)

	# Need to build the topology.txt file once.
	# Do it now as if done later it will be created
	# once per process and could potentially race with other processes
	# that need to create this file.
	#
	# The assumption is that any processes running are of the same topology
	Simulation.writeTopologyFile(configuration.topology.nodes)

for (k, v) in vars(a.args).items():
	print("{}={}".format(k, v))

Metrics.Metrics.printHeader()

# Because of the way TOSSIM is architectured each individual simulation
# needs to be run in a separate process.
if a.args.mode == "GUI":
	import simulator.DoRun

else:
	def runner(args):
		print_lock = Lock()

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

			except (KeyboardInterrupt, SystemExit) as e:
				print("Killing process due to {}".format(e), file=sys.stderr)
				process.terminate()

		max_retries = 3
		tries = 0
		done = False

		while not done and tries < max_retries:
			try:
				tries += 1
				runner_impl(args)
				done = True
			except Exception as e:
				print("Encountered (try {}): {}".format(tries, e), file=sys.stderr)
				print(traceback.format_exc(), file=sys.stderr)

	subprocess_args = ["python", "-m", "simulator.DoRun"] + sys.argv[1:]

	p = multiprocessing.Pool(a.args.thread_count)
	try:
		r = p.map_async(runner, [subprocess_args] * a.args.job_size)
		r.wait()
	except (KeyboardInterrupt, SystemExit) as e:
		print("Killing thread pool due to {}".format(e), file=sys.stderr)
		p.terminate()
	except Exception as e:
		print("Encountered: {}".format(e), file=sys.stderr)
		print(traceback.format_exc(), file=sys.stderr)
