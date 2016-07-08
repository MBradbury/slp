#!/usr/bin/env python
from __future__ import print_function

import argparse
import importlib
import sys

from data import testbed_manager

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Testbed Deployment", add_help=True)
    parser.add_argument("name", type=str)
    parser.add_argument("action", type=str, choices=["list", "update", "build", "deploy", "read-logs"])

    args = parser.parse_args(sys.argv[1:])

    testbed = testbed_manager.load(args.name)

    if args.action == "list":

        nodes = testbed.nodes()

        for (name, ip, mac) in nodes:
            print("{} {} {}".format(
                name.ljust(len("ailuropoda-xxx")),
                ip.ljust(len("xxx.xxx.xxx.xxx")),
                mac.ljust(len("xx:xx:xx:xx:xx:xx"))
            ))

    if args.action == "update":

        # Update the hg and git repos across the testbed

        pass

    elif args.action == "build":
        from data.run.driver.testbed_builder import Runner as Builder

        #testbed_directory = os.path.join("testbed", self.algorithm_module.name)

        #print("Removing existing testbed directory and creating a new one")
        #recreate_dirtree(testbed_directory)

    elif args.action == "deploy":
        
        # Copy binaries to the cluster and flash the nodes with them

        pass

    elif args.action == "read-logs"

        # Get the logs off the testbed

        pass

    else:
        raise RuntimeError("Unknown action")
