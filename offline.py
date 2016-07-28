#!/usr/bin/env python
from __future__ import print_function

import argparse
import sys

parser = argparse.ArgumentParser(description="Offline processor", add_help=True)

subparsers = parser.add_subparsers(dest='action')

subparser = subparsers.add_parser("visualise")
subparser.add_argument("--merged-log", type=str, required=True)

subparser = subparsers.add_parser("analyse")
subparser.add_argument("--merged-log", type=str, required=True)

args = parser.parse_args(sys.argv[1:])

if args.action == "visualise":
	pass

elif args.action == "analyse":
	pass

else:
	raise RuntimeError("Unknown action {}".format(args.action))
