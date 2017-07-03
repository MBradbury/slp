from __future__ import print_function, division

from pprint import pprint

import numpy as np

from data import results

from simulator.common import global_parameter_names

import algorithm

def transform_key(key, to_remove_idx):
	return tuple(np.delete(key, to_remove_idx))

def transform_results_data(data, to_remove):

	to_remove_idx = tuple([global_parameter_names.index(name) for name in to_remove])

	return {transform_key(k, to_remove_idx): v for (k, v) in data.items()}

def all_results(algorithms):
	modules = [algorithm.import_algorithm(algo) for algo in algorithms]

	module_results = [
		results.Results(
            module.result_file_path,
            parameters=module.local_parameter_names,
            results=('captured', 'received ratio', 'normal latency',  'norm(sent,time taken)'))

		for module
		in modules
	]

	parameters = {}
	for result in module_results:
		parameters.update(dict(result.parameters()))

	parameters_to_remove = [k for (k, v) in parameters.items() if len(v) == 1]

	new_global_parameters = tuple([name for name in global_parameter_names if name not in parameters_to_remove])

	results_data = [transform_results_data(result.data, parameters_to_remove) for result in module_results]

	
	combined_data = {}

	for (algo_name, result_data) in zip(algorithms, results_data):

		for (global_params, items1) in result_data.items():

			if global_params not in combined_data:
				combined_data[global_params] = {}

			for (source_period, items2) in items1.items():

				if source_period not in combined_data[global_params]:
					combined_data[global_params][source_period] = {}

				for (local_params, algo_results) in items2.items():

					combined_data[global_params][source_period][(algo_name, local_params)] = algo_results

	return new_global_parameters, combined_data


def remove_dominated_items(items):

	new_items = {}

	# Items is a dict of (algo_name, local_params) to the results

	items_list = items.items()

	for (key, value) in items_list:

		is_dominated = False

		for (other_key, other_value) in items_list:
			if key is other_key:
				continue

			if other_value > value:
				is_dominated = True
				print("{} is dominated by {} due to {} < {}".format(key, other_key, value, other_value))
				break

		if not is_dominated:
			new_items[key] = value

	return new_items


def filter_strictly_worse(results_data):
	filtered_data = {}

	for (global_params, items1) in result_data.items():

		if global_params not in filtered_data:
			filtered_data[global_params] = {}

		for (source_period, items2) in items1.items():

			filtered_data[global_params][source_period] = remove_dominated_items(items)

	return filtered_data


algorithm_names = ["protectionless", "adaptive_spr", "ilprouting"]

new_global_parameters, res = all_results(algorithm_names)

pprint(res)

filtered_res = filter_strictly_worse(res)

pprint(filtered_res)
