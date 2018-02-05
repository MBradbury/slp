#!/usr/bin/env python3
import sys

import numpy as np

import algorithm

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

    algorithm_module = algorithm.import_algorithm(algorithm_name, extras=["CommandLine"])

    # Raise all numpy errors
    np.seterr(all='raise')

    cli = algorithm_module.CommandLine.CLI()
    cli.run(args)
