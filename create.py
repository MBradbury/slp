#!/usr/bin/env python

from __future__ import print_function

import os, sys, importlib

from data.util import create_dirtree

import numpy

args = []
if len(sys.argv[1:]) == 0:
    raise RuntimeError("No arguments provided!")
else:
    args = sys.argv[1:]

algorithm_name = args[0]
args = args[1:]

algorithm = importlib.import_module("algorithm.{}".format(algorithm_name))

# Raise all numpy errors
numpy.seterr(all='raise')

create_dirtree(algorithm.results_path)
create_dirtree(algorithm.graphs_path)

cli = algorithm.CommandLine.CLI()
cli.run(args)
