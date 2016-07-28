#!/usr/bin/env python
from __future__ import print_function

import argparse
import copy
import importlib
import sys

import simulator.Attacker as Attacker
import simulator.Configuration as Configuration
from simulator.Simulation import OfflineSimulation

parser = argparse.ArgumentParser(description="Offline processor", add_help=True)

subparsers = parser.add_subparsers(dest='action')

subparser = subparsers.add_parser("visualise")
subparser.add_argument("--merged-log", type=str, required=True)

subparser = subparsers.add_parser("analyse")
subparser.add_argument("--merged-log", type=str, required=True)

subparser.add_argument("--algorithm", type=str, required=True)
subparser.add_argument("-am", "--attacker-model", type=Attacker.eval_input, required=True)
subparser.add_argument("-c", "--configuration", type=str, required=True, choices=Configuration.names())
subparser.add_argument("-safety", "--safety-period", type=float, required=True)
subparser.add_argument("--seed", type=int, required=False)

args = parser.parse_args(sys.argv[1:])

if args.action == "visualise":
    pass

elif args.action == "analyse":
    
    configuration = Configuration.create_specific(args.configuration, None, 4.5)

    with OfflineSimulation("algorithm." + args.algorithm, configuration, args, args.merged_log) as sim:

        # Create a copy of the provided attacker model
        attacker = copy.deepcopy(args.attacker_model)

        # Setup each attacker model
        attacker.setup(sim, configuration.sink_id, 0)

        sim.add_attacker(attacker)

        sim.run()

        sim.metrics.print_results()


else:
    raise RuntimeError("Unknown action {}".format(args.action))
