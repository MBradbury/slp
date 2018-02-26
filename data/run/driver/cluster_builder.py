import os
import shlex
import shutil

import data.util
from data import submodule_loader
from data.progress import Progress

import algorithm

import simulator.sim
from simulator import Builder
from simulator import Configuration

class Runner(object):
    required_safety_periods = True

    def __init__(self, sim_name):
        self.sim_name = sim_name
        self._sim = submodule_loader.load(simulator.sim, self.sim_name)
        self._progress = Progress("building file")
        self.total_job_size = None
        self._jobs_executed = 0

    def add_job(self, options, name, estimated_time):
        print(name)

        if not self._progress.has_started():
            self._progress.start(self.total_job_size)

        # Create the target directory
        target_directory = name[:-len(".txt")]

        data.util.create_dirtree(target_directory)

        # Parse options
        options = shlex.split(options)
        module, argv = options[0], options[1:]
        module_path = module.replace(".", "/")

        a = self.parse_arguments(module, argv)

        # Build the binary
        print(f"Building for {self.sim_name}")

        build_result = self._sim.build(module, a)

        print(f"Build finished with result {build_result}...")

        # Previously there have been problems with the built files not
        # properly having been flushed to the disk before attempting to move them.

        print(f"Copying files from {module_path} to {target_directory}...")

        files_to_copy = (
            "Analysis.py",
            "Arguments.py",
            "CommandLine.py",
            "Metrics.py",
            "__init__.py",
        )
        for name in files_to_copy:
            shutil.copy(os.path.join(module_path, name), target_directory)

        if self.sim_name == "tossim":
            files_to_move = (
                "app.xml",
                "_TOSSIM.so",
                "TOSSIM.py",
            )
            for name in files_to_move:
                shutil.move(os.path.join(module_path, name), target_directory)


        print("All Done!")

        self._progress.print_progress(self._jobs_executed)

        self._jobs_executed += 1

    def mode(self):
        return "CLUSTER"

    @staticmethod
    def parse_arguments(module, argv):
        arguments_module = algorithm.import_algorithm(module, extras=["Arguments"])

        a = arguments_module.Arguments.Arguments()
        a.parse(argv)
        return a

    @staticmethod
    def build_arguments(a):
        build_args = a.build_arguments()

        configuration = Configuration.create(a.args.configuration, a.args)

        build_args.update(configuration.build_arguments())

        return build_args
