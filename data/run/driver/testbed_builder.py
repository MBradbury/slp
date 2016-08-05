from __future__ import print_function, division

import datetime
import importlib
import os
import shlex
import shutil
import time
import timeit

import data.util

from simulator import Builder
from simulator import Configuration

class Runner:
    def __init__(self, testbed):
        self._start_time = timeit.default_timer()
        self.total_job_size = None
        self._jobs_executed = 0

        self.testbed = testbed

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

        # These are the arguments that will be passed to the compiler
        build_args = self.build_arguments(a)
        build_args["TESTBED"] = self.testbed.name()
        build_args["USE_SERIAL_PRINTF"] = 1

        print("Building for {}".format(build_args))

        build_result = Builder.build_actual(module_path, self.testbed.platform(), **build_args)

        print("Build finished with result {}, waiting for a bit...".format(build_result))

        # For some reason, we seemed to be copying files before
        # they had finished being written. So wait a  bit here.
        time.sleep(1)

        print("Copying files to {}...".format(target_directory))

        files_to_move = [
            "app.c",
            "ident_flags.txt",
            "main.exe",
            "main.ihex",
            "main.srec",
            "tos_image.xml",
            "wiring-check.xml",
        ]
        for name in files_to_move:
            try:
                shutil.copy(os.path.join(module_path, "build", self.testbed.platform(), name), target_directory)
            except IOError as ex:
                print("Not copying {} due to {}".format(name, ex))

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
        return "TESTBED"

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
