#!/usr/bin/python

from __future__ import print_function

import os, sys, struct, importlib, subprocess

from simulator.Attacker import Attacker
from simulator.Builder import build
from simulator.Topology import *
from simulator.Configuration import *
from simulator.Simulation import Simulation
from simulator.SubprocessPool import SubprocessPool

module = sys.argv[1]

Arguments = importlib.import_module("{}.Arguments".format(module))
Metrics = importlib.import_module("{}.Metrics".format(module))

a = Arguments.Arguments()
a.parse(sys.argv[2:])

build_arguments = a.getBuildArguments()

configuration = CreateSourceCorner(a.args.network_size, a.args.wireless_range - 2.5)

build_arguments.update(configuration.getBuildArguments())

if configuration.spaceBehindSink:
	build_arguments.update({"ALGORITHM": "GenericAlgorithm"})
else:
	build_arguments.update({"ALGORITHM": "FurtherAlgorithm"})

# Now build the simulation with the specified arguments
build(module, **build_arguments)

Metrics.Metrics.printHeader()

# Because of the way TOSSIM is architectured each individual simulation
# needs to be run in a separate process.
if a.args.mode == "GUI":
	import simulator.DoRun

else:
	subprocess_args = ["python", "-m", "simulator.DoRun"] + sys.argv[1:]

	def runner():
		return subprocess.Popen(subprocess_args, stdout=subprocess.PIPE)

	def callback(proc):
		for line in proc.stdout:
			print(line, end="")

	p = SubprocessPool(a.args.thread_count, runner, callback)
	p.run(a.args.job_size)
