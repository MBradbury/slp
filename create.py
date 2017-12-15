#!/usr/bin/env python3
from __future__ import print_function

import importlib
import sys

import numpy as np

from data.util import create_dirtree

if __name__ == "__main__":
    from simulator import dependency
    dependency.check_all()

    args = []
    if len(sys.argv[1:]) == 0:
        raise RuntimeError("No arguments provided! Please provide the name of the algorithm.")
    else:
        args = sys.argv[1:]

    algorithm_name = args[0]
    args = args[1:]

    algorithm = importlib.import_module(f"algorithm.{algorithm_name}")
    CommandLine = importlib.import_module(f"algorithm.{algorithm_name}.CommandLine")

    # Raise all numpy errors
    np.seterr(all='raise')

    create_dirtree(algorithm.results_path)
    create_dirtree(algorithm.graphs_path)

    cli = CommandLine.CLI()
    cli.run(args)
