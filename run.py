#!/usr/bin/python

from __future__ import print_function

import sys, importlib, subprocess, multiprocessing

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
	subprocess_args = ["python", "-m", "simulator.DoRun"] + sys.argv[1:]

	def runner(args):
		process = subprocess.Popen(args, stdout=subprocess.PIPE)
		try:
			process.wait()
		except (KeyboardInterrupt, SystemExit):
			process.terminate()

		for line in process.stdout:
			print(line, end="")

	p = multiprocessing.Pool(a.args.thread_count)
	try:
		r = p.map_async(runner, [subprocess_args] * a.args.job_size)
		r.wait()
	except (KeyboardInterrupt, SystemExit):
		p.terminate()
