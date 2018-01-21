
from collections import OrderedDict
import math
import os.path
import sys

from more_itertools import unique_everseen

import numpy as np

from data import results, submodule_loader

from simulator import Attacker
import simulator.sim

class MissingSafetyPeriodError(RuntimeError):
    def __init__(self, key, source_period, safety_periods):
        super(MissingSafetyPeriodError, self).__init__()
        self.key = key
        self.source_period = source_period
        self.safety_periods = safety_periods

    def __str__(self):
        return "Failed to find the safety period key {} and source period {}".format(self.key, repr(self.source_period))

def _argument_name_to_parameter(argument_name):
    return "--" + argument_name.replace(" ", "-")

class RunSimulationsCommon(object):
    def __init__(self, sim_name, driver, algorithm_module, result_path, skip_completed_simulations=True,
                 safety_periods=None, safety_period_equivalence=None):
        self.sim_name = sim_name
        self.driver = driver
        self.algorithm_module = algorithm_module
        self._result_path = result_path
        self._skip_completed_simulations = skip_completed_simulations
        self._safety_periods = safety_periods
        self._safety_period_equivalence = safety_period_equivalence

        self._global_parameter_names = submodule_loader.load(simulator.sim, self.sim_name).global_parameter_names

        if not os.path.exists(self._result_path):
            raise RuntimeError(f"{self._result_path} is not a directory")

        self._existing_results = {}

    def run(self, repeats, argument_names, argument_product, time_estimator=None, verbose=False):

        if len(argument_names) != len(argument_product[0]):
            raise RuntimeError("Number of argument names ({}) does not equal number of arguments ({})".format(
                len(argument_names), len(argument_product[0])))

        if self._skip_completed_simulations:
            self._load_existing_results(argument_names)
        
        self.driver.total_job_size = len(argument_product)

        for arguments in argument_product:
            darguments = OrderedDict(zip(argument_names, arguments))

            if repeats is not None:
                repeats_performed = self._get_repeats_performed(darguments)

                if repeats_performed >= repeats:
                    print(f"Already gathered results for {darguments} with {repeats} repeats, so skipping it.", file=sys.stderr)
                    self.driver.total_job_size -= 1
                    continue
                else:
                    print(f"Already gathered {repeats_performed} results for {darguments} so only performing {repeats - repeats_performed}", file=sys.stderr)
                    repeats -= repeats_performed

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

            opt_items = [f"{k} \"{v}\"" for (k, v) in opts.items()]

            if verbose:
                opt_items.append("--verbose")

            options = f'algorithm.{self.algorithm_module.name} {self.sim_name} {self._mode()} {" ".join(opt_items)}'

            filename = os.path.join(
                self._result_path,
                '-'.join(map(self._sanitize_job_name, arguments)) + f"-{self.sim_name}.txt"
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

        if mode == "TESTBED":
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

        key = [
            self._prepare_argument_name(name, darguments)
            for name
            in self._global_parameter_names
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
                    global_param_index = self._global_parameter_names.index(global_param)

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
        results_file_path = self.algorithm_module.result_file_path(self.sim_name)
        try:
            results_summary = results.Results(
                self.sim_name, results_file_path,
                parameters=argument_names[len(self._global_parameter_names):],
                results=('repeats',))

            # (size, config, attacker_model, noise_model, communication_model, distance, period) -> repeats
            self._existing_results = results_summary.parameter_set()
        except IOError as e:
            message = str(e)
            if 'No such file or directory' in message:
                raise RuntimeError(f"The results file {results_file_path} is not present. Perhaps rerun the command with '--no-skip-complete'?")
            else:
                raise

    def _get_repeats_performed(self, darguments):
        if not self._skip_completed_simulations:
            return 0

        key = tuple(self._prepare_argument_name(name, darguments) for name in darguments)

        if key not in self._existing_results:
            print("Unable to find the key {} in the existing results. Will now run the simulations for these parameters.".format(key), file=sys.stderr)
            return 0

        # Check that more than enough jobs were done
        return self._existing_results[key]

    @staticmethod
    def _sanitize_job_name(name):
        name = str(name)

        # These characters cause issues in file names.
        # They also need to be valid python module names.
        chars = ".,()={}'\""

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

    #extra_arguments = ('rf power', 'low power listening')

    # Filter out invalid parameters to pass onwards
    non_arguments = ('network size', 
                     'attacker model', 'noise model',
                     'communication model', 'distance',
                     'latest node start time')

    def __init__(self, sim_name, driver, algorithm_module, result_path, skip_completed_simulations=False,
                 safety_periods=None, safety_period_equivalence=None):

        if sim_name != "real":
            raise ValueError("RunTestbedCommon must be created using the 'real' sim")

        # Do all testbed tasks
        # Testbed has no notion of safety period
        super(RunTestbedCommon, self).__init__(sim_name, driver, algorithm_module, result_path, False, None, safety_period_equivalence)

    def run(self, repeats, argument_names, argument_product, time_estimator=None, **kwargs):

        filtered_argument_names, filtered_argument_product = filter_arguments(argument_names, argument_product, self.non_arguments)

        # Check that all "node id order" parameters are topology
        nido_index = filtered_argument_names.index("node id order")
        for args in filtered_argument_product:
            if args[nido_index] != "topology":
                raise ValueError(f"Cannot run testbed with a node id order other than topology (given {args[nido_index]})")

        # Testbed has no notion of repeats
        # Also no need to estimate time
        super(RunTestbedCommon, self).run(None, filtered_argument_names, filtered_argument_product, None, **kwargs)
