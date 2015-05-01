import os, importlib, shlex, shutil

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

        print("building for {}".format(build_args))

        LocalBuilder.build(module_path, **build_args)

        files_to_move = [
            "_TOSSIMmodule.so",
            "TOSSIM.py",
            "Analysis.py",
            "Arguments.py",
            "CommandLine.py",
            "Runner.py",
            "Metrics.py",
            "__init__.py",
            "app.xml",
        ]
        for name in files_to_move:
            shutil.copy(os.path.join(module_path, name), target_directory)

        # Create the topology of this configuration
        print("Creating topology file")
        configuration = Configuration.Create(a.args.configuration, a.args)
        Simulation.Simulation.write_topology_file(configuration.topology.nodes, target_directory)

    def mode(self):
        return "CLUSTER"

    @staticmethod
    def parse_arguments(module, argv):
        Arguments = importlib.import_module("{}.Arguments".format(module))

        a = Arguments.Arguments()
        a.parse(argv)
        return a

    @staticmethod
    def build_arguments(a):
        build_args = a.build_arguments()

        configuration = Configuration.Create(a.args.configuration, a.args)

        build_args.update(configuration.build_arguments())

        return build_args
