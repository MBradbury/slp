from __future__ import print_function, division
import os, importlib, shlex, shutil, timeit, datetime

import data.util

from simulator import Builder
from simulator import Configuration, Simulation

class Runner:
    def __init__(self):
        self._start_time = timeit.default_timer()
        self.total_job_size = None
        self._jobs_executed = 0

    def add_job(self, options, name, estimated_time):
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

        build_result = Builder.build_sim(module_path, **build_args)

        print("Build finished with result {}...".format(build_result))

        # Previously there have been problems with the built files not
        # properly having been flushed to the disk before attempting to move them.

        print("Copying files from {} to {}...".format(module_path, target_directory))

        files_to_copy = [
            "Analysis.py",
            "Arguments.py",
            "CommandLine.py",
            "Metrics.py",
            "__init__.py",
        ]
        files_to_move = [
            "app.xml",
            "_TOSSIM.so",
            "TOSSIM.py",
        ]
        for name in files_to_copy:
            shutil.copy(os.path.join(module_path, name), target_directory)
        for name in files_to_move:
            shutil.move(os.path.join(module_path, name), target_directory)


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
