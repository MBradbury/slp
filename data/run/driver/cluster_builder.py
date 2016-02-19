from __future__ import print_function, division
import os, importlib, shlex, shutil, time, timeit, datetime

import data.util

from simulator import Builder as LocalBuilder
from simulator import Configuration, Simulation

class Runner:
    def __init__(self):
        self._start_time = timeit.default_timer()
        self.total_job_size = None
        self._jobs_executed = 0

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

        print("Copying files to {}...".format(target_directory))

        files_to_move = [
            "Analysis.py",
            "Arguments.py",
            "CommandLine.py",
            "Metrics.py",
            "__init__.py",
            "app.xml",
            "_TOSSIM.so",
            "TOSSIM.py",
        ]
        for name in files_to_move:
            shutil.copy(os.path.join(module_path, name), target_directory)

        # Create the topology of this configuration
        print("Creating topology file...")
        configuration = Configuration.create(a.args.configuration, a.args)
        Simulation.Simulation.write_topology_file(configuration.topology.nodes, target_directory)

        print("All Done!")

        job_num = self._jobs_executed + 1

        current_time_taken = timeit.default_timer() - self._start_time
        time_per_job = current_time_taken / job_num
        estimated_total = time_per_job * self.total_job_size
        estimated_remaining = estimated_total - current_time_taken

        current_time_taken_str = str(datetime.timedelta(seconds=current_time_taken))
        estimated_remaining_str = str(datetime.timedelta(seconds=estimated_remaining))

        print("Finished building file {} out of {}. Done {}%. Time taken {}, estimated remaining {}".format(
            job_num, self.total_job_size, (job_num / self.total_job_size) * 100.0, current_time_taken_str, estimated_remaining_str))

        print()

        self._jobs_executed += 1

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
