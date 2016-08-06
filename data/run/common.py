from __future__ import print_function, division

import os, sys, math
from collections import OrderedDict

from more_itertools import unique_everseen

import numpy as np

from data import results
import simulator.common

class RunSimulationsCommon(object):
    def __init__(self, driver, algorithm_module, result_path, skip_completed_simulations=True, safety_periods=None):
        self.driver = driver
        self.algorithm_module = algorithm_module
        self._result_path = result_path
        self._skip_completed_simulations = skip_completed_simulations
        self._safety_periods = safety_periods

        if not os.path.exists(self._result_path):
            raise RuntimeError("{} is not a directory".format(self._result_path))

        self._existing_results = {}

    @staticmethod
    def _argument_name_to_parameter(argument_name):
        argument_name = argument_name.replace(" ", "-")

        return "--" + argument_name

    @classmethod
    def _argument_name_to_stored(cls, argument_name):
        return cls._argument_name_to_parameter(argument_name)[2:].replace("-", " ")

    def run(self, repeats, argument_names, argument_product, time_estimater=None):
        if self._skip_completed_simulations:
            self._load_existing_results(argument_names)
        
        self.driver.total_job_size = len(argument_product)

        for arguments in argument_product:
            if self._already_processed(repeats, arguments):
                print("Already gathered results for {}, so skipping it.".format(arguments), file=sys.stderr)
                self.driver.total_job_size -= 1
                continue

            # Not all drivers will supply job_repeats
            job_repeats = self.driver.job_repeats if hasattr(self.driver, 'job_repeats') else 1

            opts = OrderedDict()

            if repeats is not None:
                opts["--job-size"] = int(math.ceil(repeats / job_repeats))

            if hasattr(self.driver, 'array_job_variable') and self.driver.array_job_variable is not None:
                opts["--job-id"] = self.driver.array_job_variable

            if hasattr(self.driver, 'job_thread_count') and self.driver.job_thread_count is not None:
                opts["--thread-count"] = self.driver.job_thread_count

            for (name, value) in zip(argument_names, arguments):
                flag = self._argument_name_to_parameter(name)
                opts[flag] = value

            if self._safety_periods is not None:
                safety_period = self._get_safety_period(argument_names, arguments)
                opts["--safety-period"] = safety_period

            opt_items = ["{} \"{}\"".format(k, v) for (k, v) in opts.items()]

            options = 'algorithm.{} {} '.format(self.algorithm_module.name, self.driver.mode()) + " ".join(opt_items)

            filename = os.path.join(
                self._result_path,
                '-'.join(map(self._sanitize_job_name, arguments)) + ".txt"
            )

            estimated_time = None
            if time_estimater is not None:
                estimated_time = time_estimater(*arguments)

            self.driver.add_job(options, filename, estimated_time)


    def _get_safety_period(self, argument_names, arguments):
        if self._safety_periods is None:
            return None

        key = []

        for name in simulator.common.global_parameter_names:
            value = str(arguments[argument_names.index(name)])

            key.append(value)

        # Source period is always stored as the last item in the list
        source_period = key[-1]
        key = tuple(key[:-1])

        try:
            return self._safety_periods[key][source_period]
        except KeyError as ex:
            raise KeyError("Failed to find the safety period key {} and source period {}".format(key, repr(source_period)), ex)

    def _load_existing_results(self, argument_names):
        try:
            results_summary = results.Results(
                self.algorithm_module.result_file_path,
                parameters=argument_names[len(simulator.common.global_parameter_names):],
                results=('repeats',))

            # (size, config, attacker_model, noise_model, communication_model, distance, period) -> repeats
            self._existing_results = results_summary.parameter_set()
        except IOError as e:
            message = str(e)
            if 'No such file or directory' in message:
                raise RuntimeError("The results file {} is not present. Perhaps rerun the command with 'no-skip-complete'?".format(
                    self.algorithm_module.result_file_path))
            else:
                raise

    def _already_processed(self, repeats, arguments):
        if not self._skip_completed_simulations:
            return False

        key = tuple(map(str, arguments))

        if key not in self._existing_results:
            print("Unable to find the key {} in the existing results".format(key), file=sys.stderr)
            return False

        # Check that more than enough jobs were done
        number_results = self._existing_results[key]

        return number_results >= repeats

    @staticmethod
    def _sanitize_job_name(name):

        name = str(name)

        # These characters cause issues in file names.
        # They also need to be valid python module names.
        chars = ".()="

        for char in chars:
            name = name.replace(char, "_")

        return name

class RunTestbedCommon(RunSimulationsCommon):
    def __init__(self, driver, algorithm_module, result_path, skip_completed_simulations=False, safety_periods=None):
        # Do all testbed tasks
        # Testbed has no notion of safety period
        super(RunTestbedCommon, self).__init__(driver, algorithm_module, result_path, False, None)

    def run(self, repeats, argument_names, argument_product, time_estimater=None):

        # Filter out invalid parameters to pass onwards
        to_filter = ['network size', 
                     'attacker model', 'noise model',
                     'communication model', 'distance']

        # Remove indexes
        indexes = [argument_names.index(name) for name in to_filter]

        filtered_argument_names = tuple(np.delete(argument_names, indexes))
        filtered_argument_product = [tuple(np.delete(args, indexes)) for args in argument_product]

        # Remove duplicates
        filtered_argument_product = list(unique_everseen(filtered_argument_product))

        # Testbed has no notion of repeats
        # Also no need to estimate time
        super(RunTestbedCommon, self).run(None, filtered_argument_names, filtered_argument_product, None)
