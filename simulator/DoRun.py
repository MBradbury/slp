#!/usr/bin/env python3
import sys

import simulator.sim

from data import submodule_loader

def main():
    import importlib

    module = sys.argv[1]

    Arguments = importlib.import_module(f"{module}.Arguments")

    a = Arguments.Arguments()
    a.parse(sys.argv[2:])

    sim = submodule_loader.load(simulator.sim, a.args.sim)

    result = sim.run_simulation(module, a)

    sys.exit(result)

if __name__ == "__main__":
    main()
