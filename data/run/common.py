from __future__ import print_function, division
import os, sys, math, fnmatch
from collections import OrderedDict

from data import results
from algorithm.common.CommandLineCommon import CLI as CommandLineCommon

class RunSimulationsCommon(object):
    optimisations = '-OO'

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

    def run(self, exe_path, repeats, argument_names, argument_product):
        if self._skip_completed_simulations:
            self._load_existing_results(argument_names)
        
        if not os.path.exists(exe_path):
            raise RuntimeError("The file {} doesn't exist".format(exe_path))

        self.driver.total_job_size = len(argument_product)

        for arguments in argument_product:
            if self._already_processed(repeats, arguments):
                print("Already gathered results for {}, so skipping it.".format(arguments), file=sys.stderr)
                self.driver.total_job_size -= 1
                continue

            executable = 'python {} {}'.format(
                self.optimisations,
                exe_path)

            # Not all drivers will supply job_repeats
            job_repeats = self.driver.job_repeats if hasattr(self.driver, 'job_repeats') else 1

            opts = OrderedDict()
            opts["--mode"] = self.driver.mode()
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

            options = 'algorithm.{} '.format(self.algorithm_module.name) + " ".join(opt_items)

            filename = os.path.join(
                self._result_path,
                '-'.join(map(self._sanitize_job_name, arguments)) + ".txt"
            )

            self.driver.add_job(executable, options, filename)


    def _get_safety_period(self, argument_names, arguments):
        if self._safety_periods is None:
            return None

        key = []

        for name in CommandLineCommon.global_parameter_names:
            local_key = self._argument_name_to_stored(name)

            value = str(arguments[argument_names.index(local_key)])

            key.append(value)

        # Source period is always stored as the last item in the list
        source_period = key[-1]
        key = tuple(key[:-1])

        try:
            return self._safety_periods[key][source_period]
        except KeyError as ex:
            raise KeyError("Failed to find the safety period key {} and source period {}".format(key, source_period), ex)

    def _load_existing_results(self, argument_names):
        results_summary = results.Results(
            self.algorithm_module.result_file_path,
            parameters=argument_names[len(CommandLineCommon.global_parameter_names):],
            results=('repeats',))

        # (size, config, attacker_model, noise_model, communication_model, distance, period) -> repeats
        self._existing_results = results_summary.parameter_set()

    def _already_processed(self, repeats, arguments):
        if not self._skip_completed_simulations:
            return False

        key = tuple(map(str, arguments))

        if key not in self._existing_results:
            print("Unable to find the key {} in the existing results".format(key), file=sys.stderr)
            return False

        # Check that more than enough jobs were done
        results = self._existing_results[key]

        return results >= repeats

    @staticmethod
    def _sanitize_job_name(name):

        name = str(name)

        # These characters cause issues in file names.
        # They also need to be valid python module names.
        chars = ".()="

        for char in chars:
            name = name.replace(char, "_")

        return name
