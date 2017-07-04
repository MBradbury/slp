from __future__ import print_function, division

import numpy as np

import algorithm

from data import results
from data.util import scalar_extractor

from simulator.common import global_parameter_names

class NullResultsTransformer(object):
    def __init__(self, algorithm_modules):
        self.algorithm_modules = [
            algorithm.import_algorithm(module) if isinstance(module, str) else module
            for module
            in algorithm_modules
        ]

    def transform(self, result_names):
        return [
            results.Results(
                module.result_file_path,
                parameters=module.local_parameter_names,
                results=result_names)

            for module
            in self.algorithm_modules
        ]

class EliminateDominatedResultsTransformer(object):
    def __init__(self, algorithm_modules, comparison_functions, remove_redundant_parameters=False):
        self.algorithm_modules = [
            algorithm.import_algorithm(module) if isinstance(module, str) else module
            for module
            in algorithm_modules
        ]

        self.safety_factor_indexes = {}

        self.comparison_functions = comparison_functions
        self.remove_redundant_parameters = remove_redundant_parameters

        self.dominated_data = None

    def transform(self, result_names):

        all_result_names = tuple(set(result_names) | set(self.comparison_functions.keys()))

        module_results = [
            results.Results(
                module.result_file_path,
                parameters=module.local_parameter_names,
                results=all_result_names)

            for module
            in self.algorithm_modules
        ]

        self.global_parameter_names = global_parameter_names[:-1]

        for (module, module_result) in zip(self.algorithm_modules, module_results):
            self.safety_factor_indexes[module.name] = module_result.parameter_names.index("safety factor")

        if self.remove_redundant_parameters:
            self._remove_redundant_parameters(module_results)

        # Combine everything
        combined_results = self._combine_results(module_results)

        # Find the dominating data
        dominating_data, self.dominated_data = self._filter_strictly_worse(combined_results, all_result_names)

        # Split up the data back into the individual chunks
        split_results = self._convert_dominating_to_individual(dominating_data)

        # Reassign it
        for (module_result, module) in zip(module_results, self.algorithm_modules):
            module_result.data = split_results[module.name]
            module_result.global_parameter_names = self.global_parameter_names

        return module_results

    def _remove_redundant_parameters(self, module_results):
        parameters = {}
        for module_result in module_results:
            parameters.update(dict(module_result.parameters()))

        parameters_to_remove = [k for (k, v) in parameters.items() if len(v) == 1]

        self.global_parameter_names = tuple([name for name in self.global_parameter_names if name not in parameters_to_remove])

        for module_result in module_results:
            module_result.data = self._transform_results_data(module_result.data, parameters_to_remove)

    @staticmethod
    def _transform_key(key, to_remove_idx):
        return tuple(np.delete(key, to_remove_idx))

    def _transform_results_data(self, data, to_remove):
        to_remove_idx = tuple([self.global_parameter_names.index(name) for name in to_remove if name in self.global_parameter_names])

        return {self._transform_key(k, to_remove_idx): v for (k, v) in data.items()}

    def _combine_results(self, module_results):
        combined_data = {}

        for (algo, module_result) in zip(self.algorithm_modules, module_results):

            safety_factor_idx = self.safety_factor_indexes[algo.name]

            for (global_params, items1) in module_result.data.items():
                for (source_period, items2) in items1.items():
                    for (local_params, algo_results) in items2.items():

                        safety_factor = local_params[safety_factor_idx]

                        new_local_params = self._transform_key(local_params, safety_factor_idx)

                        combined_data.setdefault(global_params, {}).setdefault(source_period, {}).setdefault(safety_factor, {})[(algo.name, new_local_params)] = algo_results

        return combined_data


    def _does_value_dominate(self, value, other_value, result_names):
        result = True

        for (name, fn) in self.comparison_functions.items():
            name_idx = result_names.index(name)

            v = value[name_idx]
            ov = other_value[name_idx]

            result &= fn(v, ov)

        return result

    def _remove_dominated_items(self, items, result_names):
        new_items = {}
        dominated_items = []

        # Items is a dict of (algo_name, local_params) to the results

        items_list = items.items()

        for (key, value) in items_list:
            value = tuple(map(scalar_extractor, value))

            is_dominated = False

            for (other_key, other_value) in items_list:
                if key == other_key:
                    continue

                other_value = tuple(map(scalar_extractor, other_value))

                if self._does_value_dominate(other_value, value, result_names):
                    is_dominated = True
                    print("{} ({}) is dominated by {} ({})".format(key, value, other_key, other_value))

                    dominated_items.append((key, value, other_key, other_value))
                    break

            if not is_dominated:
                new_items[key] = value

        return new_items, dominated_items


    def _filter_strictly_worse(self, combined_data, result_names):
        dominating_data = {}
        dominated_data = {}

        for (global_params, items1) in combined_data.items():
            for (source_period, items2) in items1.items():
                for (safety_factor, items3) in items2.items():

                    dominating_items, dominated_items = self._remove_dominated_items(items3, result_names)

                    dominating_data.setdefault(global_params, {}).setdefault(source_period, {})[safety_factor] = dominating_items
                    dominated_data.setdefault(global_params, {}).setdefault(source_period, {})[safety_factor] = dominated_items

        return dominating_data, dominated_data

    def _convert_dominating_to_individual(self, dominating_data):
        res = {}

        for (global_params, items1) in dominating_data.items():
            for (source_period, items2) in items1.items():
                for (safety_factor, items3) in items2.items():
                    for ((algo_name, new_local_params), results) in items3.items():

                        local_params = tuple(np.insert(new_local_params, self.safety_factor_indexes[algo_name], [safety_factor]))

                        res.setdefault(algo_name, {}).setdefault(global_params, {}).setdefault(source_period, {})[local_params] = results

        return res
