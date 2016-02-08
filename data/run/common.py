from __future__ import print_function, division
import os, sys, math, fnmatch
from collections import OrderedDict

class RunSimulationsCommon(object):
    optimisations = '-OO'

    def __init__(self, driver, algorithm_module, result_path, skip_completed_simulations=True, safety_periods=None):
        self.driver = driver
        self.algorithm_module = algorithm_module
        self._result_path = result_path
        self._skip_completed_simulations = skip_completed_simulations
        self.safety_periods = safety_periods

        if not os.path.exists(self._result_path):
            raise RuntimeError("{} is not a directory".format(self._result_path))

        self._existing_results = {}

    def run(self, exe_path, repeats, argument_names, argument_product):
        if self._skip_completed_simulations:
            self._check_existing_results(argument_names)
        
        if not os.path.exists(exe_path):
            raise RuntimeError("The file {} doesn't exist".format(exe_path))

        self.driver.total_job_size = len(argument_product)

        for arguments in argument_product:
            if not self._already_processed(repeats, arguments):

                executable = 'python {} {}'.format(
                    self.optimisations,
                    exe_path)

                opts = OrderedDict()
                opts["--mode"] = self.driver.mode()
                opts["--job-size"] = int(math.ceil(repeats / self.driver.job_repeats))

                if self.driver.array_job_variable is not None:
                    opts["--job-id"] = self.driver.array_job_variable

                if hasattr(self.driver, 'job_thread_count') and self.driver.job_thread_count is not None:
                    opts["--thread-count"] = self.driver.job_thread_count

                for (name, value) in zip(argument_names, arguments):
                    flag = "--" + name.replace("_", "-")
                    opts[flag] = value

                if self.safety_periods is not None:
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
        if self.safety_periods is None:
            return None

        communication_model = str(arguments[argument_names.index('communication_model')])
        noise_model = str(arguments[argument_names.index('noise_model')])
        attacker_model = str(arguments[argument_names.index('attacker_model')])
        configuration = str(arguments[argument_names.index('configuration')])
        size = int(arguments[argument_names.index('network_size')])
        source_period = str(arguments[argument_names.index('source_period')])

        key = (size, configuration, attacker_model, noise_model, communication_model)

        try:
            return self.safety_periods[key][source_period]
        except KeyError as ex:
            raise KeyError("Failed to find the safety period key {} and source period {}".format(key, source_period), ex)

    def _check_existing_results(self, argument_names):
        self._existing_results = {}

        # The output files we need to process
        files = fnmatch.filter(os.listdir(self._result_path), '*.txt')

        for infile in files:
            with open(os.path.join(self._result_path, infile)) as f:

                fileopts = {}

                seen_hash = False
                results_count = 0

                for line in f:
                    line = line.strip()

                    if '=' in line:
                        # We are reading the options so record them
                        opt = line.split('=', 1)

                        fileopts[opt[0]] = opt[1]

                    elif line.startswith('#'):
                        seen_hash = True

                    # Count result lines
                    if seen_hash and '|' in line and not line.startswith('#'):
                        results_count += 1

                if len(fileopts) != 0:
                    key = tuple([fileopts[name] for name in argument_names])
                    value = (int(fileopts['job_size']), results_count)

                    print("Added the key {} with value {} to the existing results".format(key, value), file=sys.stderr)

                    self._existing_results[key] = value

    def _already_processed(self, repeats, arguments):
        if not self._skip_completed_simulations:
            return False

        key = tuple(map(str, arguments))

        if key not in self._existing_results:
            print("Unable to find the key {} in the existing results".format(key), file=sys.stderr)
            return False

        # Check that more than enough jobs were done
        (jobs, results) = self._existing_results[key]

        # If the number of jobs recorded in the file and the number of jobs
        # actually executed are greater than or equal to the number of jobs
        # requested then everything is okay.
        return jobs >= repeats and results >= repeats

    @staticmethod
    def _sanitize_job_name(name):

        name = str(name)

        # These characters cause issues in file names.
        # They also need to be valid python module names.
        chars = ".()="

        for char in chars:
            name = name.replace(char, "_")

        return name
