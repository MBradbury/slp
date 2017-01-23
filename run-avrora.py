#!/usr/bin/env python
from __future__ import print_function, division

import os
import subprocess
import sys

from data.cycle_accurate import avrora

def main(argv):
    module = argv[1]

    # Build the binaries
    from data.run.driver.cycle_accurate_builder import Runner as Builder

    from simulator import Configuration

    # Only check dependencies on non-cluster runs
    # Cluster runs will have the dependencies checked in create.py
    from simulator import dependency
    dependency.check_all()

    target = module.replace(".", "/") + ".txt"

    builder = Builder(avrora)
    builder.total_job_size = 1
    a, module, module_path, target_directory = builder.add_job(" ".join(argv[1:]), target)

    configuration = Configuration.create(a.args.configuration, a.args)

    from datetime import datetime
    import numpy

    # Print out the versions of slp-algorithms-tinyos and tinyos being used
    try:
        slp_algorithms_version = subprocess.check_output("hg id -n -i -b -t", shell=True)
    except subprocess.CalledProcessError:
        slp_algorithms_version = "<unknown hg rev>"

    try:
        tinyos_version = subprocess.check_output("git rev-parse HEAD", shell=True, cwd=os.environ["TOSROOT"])
    except subprocess.CalledProcessError:
        tinyos_version = "<unknown git rev>"
    except KeyError:
        tinyos_version = "<unknown tinyos dir>"

    print("@version:python={}".format(sys.version.replace("\n", " ")))
    print("@version:numpy={}".format(numpy.__version__))

    print("@version:slp-algorithms={}".format(slp_algorithms_version.strip()))
    print("@version:tinyos={}".format(tinyos_version.strip()))

    # Print other potentially useful meta data
    print("@date:{}".format(str(datetime.now())))
    print("@host:{}".format(os.uname()))

    # Print out the argument settings
    for (k, v) in vars(a.args).items():
        if k not in a.arguments_to_hide:
            print("{}={}".format(k, v))

    # Make sure this header has been written
    sys.stdout.flush()

    avrora_path = "/home/matt/wsn/avrora/avrora-beta-1.7.117.jar"

    options = {
        "platform": "micaz",
        "simulation": "sensor-network",
        "seconds": "30",
        "monitors": "energy",
        "radio-range": a.args.distance + 0.25,
        "nodecount": str(configuration.size()),
        "topology": "static",
        "topology-file": os.path.join(target_directory, "topology.txt"),
        "random-seed": a.args.seed,
    }

    target_file = os.path.join(target_directory, "main.elf")

    options_string = " ".join("-{}={}".format(k,v) for (k,v) in options.items())

    #avrora -platform=micaz -simulation=sensor-network -seconds=30 -monitors=energy -radio-range=5 -nodes=121 -topology=static -topology-file=topology.txt main.elf

    command = "java -jar {} {} {}".format(avrora_path, options_string, target_file)

    print("@command:{}".format(command))

    subprocess.check_call(command, shell=True)

if __name__ == "__main__":
    main(sys.argv)
