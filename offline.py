#!/usr/bin/env python
from __future__ import print_function

import argparse
import copy
import importlib
import sys

import simulator.Attacker as Attacker
import simulator.Configuration as Configuration

parser = argparse.ArgumentParser(description="Offline processor", add_help=True)

parser.add_argument("--merged-log", type=str, required=True)

parser.add_argument("--algorithm", type=str, required=True)
parser.add_argument("-am", "--attacker-model", type=Attacker.eval_input, required=True)
parser.add_argument("-c", "--configuration", type=str, required=True, choices=Configuration.names())
parser.add_argument("-safety", "--safety-period", type=float, required=True)
parser.add_argument("--seed", type=int, required=False)

parser.add_argument("--gui", action="store_true", default=False, required=False)
parser.add_argument("--gui-scale", type=int, required=False, default=6)

args = parser.parse_args(sys.argv[1:])

if args.gui:
    from simulator.TosVis import GuiOfflineSimulation as OfflineSimulation
else:
    from simulator.Simulation import OfflineSimulation

configuration = Configuration.create_specific(args.configuration, None, 4.5)

with OfflineSimulation("algorithm." + args.algorithm, configuration, args, args.merged_log) as sim:

    # Create a copy of the provided attacker model
    attacker = copy.deepcopy(args.attacker_model)

    # Setup each attacker model
    attacker.setup(sim, configuration.sink_id, 0)

    sim.add_attacker(attacker)

    sim.run()

    sim.metrics.print_results()
