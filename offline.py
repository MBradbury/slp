#!/usr/bin/env python
from __future__ import print_function

import argparse
import importlib
import sys

import simulator.Attacker as Attacker
import simulator.Configuration as Configuration

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

args = parser.parse_args(sys.argv[1:])

if args.action == "visualise":
	pass

elif args.action == "analyse":
	Metrics = importlib.import_module("algorithm.{}.Metrics".format(args.algorithm))

	with open(args.merged_log, 'r'):
		pass

else:
	raise RuntimeError("Unknown action {}".format(args.action))
