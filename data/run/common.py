from __future__ import print_function, division

from collections import OrderedDict
import math
import os.path
import sys

from more_itertools import unique_everseen

import numpy as np

from data import results
import simulator.common
from simulator import Attacker

class MissingSafetyPeriodError(RuntimeError):
    def __init__(self, key, source_period, safety_periods):
        self.key = key
        self.source_period = source_period
        self.safety_periods = safety_periods

    def __str__(self):
        return "Failed to find the safety period key {} and source period {}".format(self.key, repr(self.source_period))

def _argument_name_to_parameter(argument_name):
    return "--" + argument_name.replace(" ", "-")

class RunSimulationsCommon(object):
    def __init__(self, sim, driver, algorithm_module, result_path, skip_completed_simulations=True,
                 safety_periods=None, safety_period_equivalence=None):
        self.sim = sim
        self.driver = driver
        self.algorithm_module = algorithm_module
        self._result_path = result_path
        self._skip_completed_simulations = skip_completed_simulations
        self._safety_periods = safety_periods
        self._safety_period_equivalence = safety_period_equivalence

        if not os.path.exists(self._result_path):
            raise RuntimeError("{} is not a directory".format(self._result_path))

        self._existing_results = {}

    def run(self, repeats, argument_names, argument_product, time_estimator=None):
        if self._skip_completed_simulations:
            self._load_existing_results(argument_names)
        
        self.driver.total_job_size = len(argument_product)

        for arguments in argument_product:
            darguments = OrderedDict(zip(argument_names, arguments))

            if self._already_processed(repeats, darguments):
                print("Already gathered results for {} with {} repeats, so skipping it.".format(darguments, repeats), file=sys.stderr)
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

            for (name, value) in darguments.items():
                flag = _argument_name_to_parameter(name)
                opts[flag] = value

            if self._safety_periods is not None:
                safety_period = self._get_safety_period(darguments)
                opts["--safety-period"] = safety_period

            opt_items = ["{} \"{}\"".format(k, v) for (k, v) in opts.items()]

            options = 'algorithm.{} {} {} '.format(self.algorithm_module.name, self.sim, self._mode())
            options +=" ".join(opt_items)

            filename = os.path.join(
                self._result_path,
                '-'.join(map(self._sanitize_job_name, arguments)) + "-{}.txt".format(self.sim)
            )

            estimated_time = None
            if time_estimator is not None:
                estimated_time = time_estimator(
                    darguments,
                    safety_period=opts.get("--safety-period"),
                    job_size=opts.get("--job-size"),
                    thread_count=opts.get("--thread-count")
                )

            self.driver.add_job(options, filename, estimated_time)

    def _mode(self):
        mode = self.driver.mode()

        if mode in ("TESTBED", "CYCLEACCURATE"):
            return "SINGLE"
        else:
            return mode

    def _prepare_argument_name(self, name, darguments):
        value = darguments[name]

        if name == 'attacker model':
            # Attacker models are special. Their string format is likely to be different
            # from what is specified in Parameters.py, as the string format prints out
            # argument names.
            return str(Attacker.eval_input(value))
        else:
            return str(value)


    def _get_safety_period(self, darguments):
        if self._safety_periods is None:
            return None

        global_parameter_names = simulator.common.global_parameter_names

        key = [
            self._prepare_argument_name(name, darguments)
            for name
            in global_parameter_names
        ]

        # Source period is always stored as the last item in the list
        source_period = key[-1]
        key = tuple(key[:-1])

        try:
            return self._safety_periods[key][source_period]
        except KeyError as ex:
            if self._safety_period_equivalence is None:
                raise MissingSafetyPeriodError(key, source_period, self._safety_periods)
            else:
                keys_to_try = []

                # There exist some safety period equivalences, so lets try some
                for (global_param, replacements) in self._safety_period_equivalence.items():
                    global_param_index = global_parameter_names.index(global_param)

                    for (search, replace) in replacements.items():
                        if key[global_param_index] == search:

                            new_key = key[:global_param_index] + (replace,) + key[global_param_index+1:]

                            keys_to_try.append(new_key)

                # Try each of the possible combinations
                for key_attempt in keys_to_try:
                    try:
                        return self._safety_periods[key_attempt][source_period]
                    except KeyError:
                        pass

                # If we couldn't find one, then raise the exception
                raise MissingSafetyPeriodError([key] + keys_to_try, source_period, self._safety_periods)


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
                raise RuntimeError("The results file {} is not present. Perhaps rerun the command with '--no-skip-complete'?".format(
                    self.algorithm_module.result_file_path))
            else:
                raise

    def _already_processed(self, repeats, darguments):
        if not self._skip_completed_simulations:
            return False

        key = tuple(self._prepare_argument_name(name, darguments) for name in darguments)

        if key not in self._existing_results:
            print("Unable to find the key {} in the existing results. Will now run the simulations for these parameters.".format(key), file=sys.stderr)
            return False

        # Check that more than enough jobs were done
        number_results = self._existing_results[key]

        return number_results >= repeats

    @staticmethod
    def _sanitize_job_name(name):
        name = str(name)

        # These characters cause issues in file names.
        # They also need to be valid python module names.
        chars = ".,()="

        for char in chars:
            name = name.replace(char, "_")

        return name

def filter_arguments(argument_names, argument_product, to_filter):
    # Remove indexes
    indexes = [argument_names.index(name) for name in to_filter]

    filtered_argument_names = tuple(np.delete(argument_names, indexes))
    filtered_argument_product = [tuple(np.delete(args, indexes)) for args in argument_product]

    # Remove duplicates
    filtered_argument_product = list(unique_everseen(filtered_argument_product))

    return filtered_argument_names, filtered_argument_product

class RunTestbedCommon(RunSimulationsCommon):
    def __init__(self, driver, algorithm_module, result_path, skip_completed_simulations=False,
                 safety_periods=None, safety_period_equivalence=None):
        # Do all testbed tasks
        # Testbed has no notion of safety period
        super(RunTestbedCommon, self).__init__("real", driver, algorithm_module, result_path, False, None, safety_period_equivalence)

    def run(self, repeats, argument_names, argument_product, time_estimator=None):

        # Filter out invalid parameters to pass onwards
        to_filter = ('network size', 
                     'attacker model', 'noise model',
                     'communication model', 'distance',
                     'node id order', 'latest node start time')

        filtered_argument_names, filtered_argument_product = filter_arguments(argument_names, argument_product, to_filter)

        # Testbed has no notion of repeats
        # Also no need to estimate time
        super(RunTestbedCommon, self).run(None, filtered_argument_names, filtered_argument_product, None)

class RunCycleAccurateCommon(RunSimulationsCommon):
    def __init__(self, sim, driver, algorithm_module, result_path, skip_completed_simulations=False,
                 safety_periods=None, safety_period_equivalence=None):
        # Do all cycle accurate tasks
        # Cycle Accurate has no notion of safety period
        super(RunCycleAccurateCommon, self).__init__(sim, driver, algorithm_module, result_path, False, None, safety_period_equivalence)

    def run(self, repeats, argument_names, argument_product, time_estimator=None):

        # Filter out invalid parameters to pass onwards
        to_filter = ('attacker model', 'noise model',
                     'communication model',
                     'latest node start time')

        filtered_argument_names, filtered_argument_product = filter_arguments(argument_names, argument_product, to_filter)

        # Cycle Accurate has no notion of repeats
        # Also no need to estimate time
        super(RunCycleAccurateCommon, self).run(None, filtered_argument_names, filtered_argument_product, None)
