from __future__ import print_function
import os, importlib, shlex, shutil, time

import data.util

from simulator import Builder as LocalBuilder
from simulator import Configuration, Simulation

class Runner:
    def __init__(self):
        pass

    def add_job(self, executable, options, name):
        print(name)

        # Create the target directory
        target_directory = name[:-len(".txt")]

        data.util.create_dirtree(target_directory)

        # Parse options
        options = shlex.split(options)
        module, argv = options[0], options[1:]
        module_path = module.replace(".", "/")

        a = self.parse_arguments(module, argv)

        # Build the binary
        build_args = self.build_arguments(a)        

        print("Building for {}".format(build_args))

        build_result = LocalBuilder.build(module_path, **build_args)

        print("Build finished with result {}, waiting for a bit...".format(build_result))

        # For some reason, we seemed to be copying files before
        # they had finished being written. So wait a  bit here.
        time.sleep(1)

        print("Copying files...")

        files_to_move = [
            "Analysis.py",
            "Arguments.py",
            "CommandLine.py",
            "Runner.py",
            "Metrics.py",
            "__init__.py",
            "app.xml",
            "_TOSSIMmodule.so",
            "TOSSIM.py",
        ]
        for name in files_to_move:
            shutil.copy(os.path.join(module_path, name), target_directory)

        # Create the topology of this configuration
        print("Creating topology file...")
        configuration = Configuration.create(a.args.configuration, a.args)
        Simulation.Simulation.write_topology_file(configuration.topology.nodes, target_directory)

        print("All Done!")
        print()

    def mode(self):
        return "CLUSTER"

    @staticmethod
    def parse_arguments(module, argv):
        arguments_module = importlib.import_module("{}.Arguments".format(module))

        a = arguments_module.Arguments()
        a.parse(argv)
        return a

    @staticmethod
    def build_arguments(a):
        build_args = a.build_arguments()

        configuration = Configuration.create(a.args.configuration, a.args)

        build_args.update(configuration.build_arguments())

        return build_args
