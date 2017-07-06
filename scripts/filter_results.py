from __future__ import print_function, division

from pprint import pprint

import numpy as np

from data import results
from data.util import scalar_extractor

from simulator.common import global_parameter_names

import algorithm

comparison_functions = {
	"captured": lambda value, other_value: value < other_value,
	"received ratio": lambda value, other_value: value > other_value,
	"normal latency": lambda value, other_value: value < other_value,
	"norm(sent,time taken)": lambda value, other_value: value < other_value,
}

result_names = ('captured', 'received ratio', 'normal latency',  'norm(sent,time taken)')

safety_factor_indexes = {}

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
			results=result_names)

		for module
		in modules
	]

	for (name, module_result) in zip(algorithms, module_results):
		safety_factor_indexes[name] = module_result.parameter_names.index("safety factor")

	parameters = {}
	for result in module_results:
		parameters.update(dict(result.parameters()))

	parameters_to_remove = [k for (k, v) in parameters.items() if len(v) == 1]

	new_global_parameters = tuple([name for name in global_parameter_names[:-1] if name not in parameters_to_remove])

	results_data = [transform_results_data(result.data, parameters_to_remove) for result in module_results]

	
	combined_data = {}

	for (algo_name, result_data) in zip(algorithms, results_data):

		safety_factor_idx = safety_factor_indexes[algo_name]

		for (global_params, items1) in result_data.items():

			if global_params not in combined_data:
				combined_data[global_params] = {}

			for (source_period, items2) in items1.items():

				if source_period not in combined_data[global_params]:
					combined_data[global_params][source_period] = {}

				for (local_params, algo_results) in items2.items():

					safety_factor = local_params[safety_factor_idx]

					if safety_factor not in combined_data[global_params][source_period]:
						combined_data[global_params][source_period][safety_factor] = {}

					new_local_params = transform_key(local_params, safety_factor_idx)

					combined_data[global_params][source_period][safety_factor][(algo_name, new_local_params)] = algo_results

	return new_global_parameters, combined_data


def does_value_dominate(value, other_value):
	return all(
		comparison_functions[name](v, ov)
		for (name, v, ov)
		in zip(result_names, value, other_value)
	)

def remove_dominated_items(items):

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

			if does_value_dominate(other_value, value):
				is_dominated = True
				print("{} ({}) is dominated by {} ({})".format(key, value, other_key, other_value))

				dominated_items.append((key, value, other_key, other_value))
				break

		if not is_dominated:
			new_items[key] = value

	return new_items, dominated_items


def filter_strictly_worse(results_data):
	dominating_data = {}
	dominated_data = {}

	for (global_params, items1) in results_data.items():

		if global_params not in dominating_data:
			dominating_data[global_params] = {}
			dominated_data[global_params] = {}

		for (source_period, items2) in items1.items():

			if source_period not in dominating_data[global_params]:
				dominating_data[global_params][source_period] = {}
				dominated_data[global_params][source_period] = {}

			for (safety_factor, items3) in items2.items():

				dominating_items, dominated_items = remove_dominated_items(items3)

				dominating_data[global_params][source_period][safety_factor] = dominating_items
				dominated_data[global_params][source_period][safety_factor] = dominated_items

	return dominating_data, dominated_data

def convert_dominating_to_individual(dominating_data):

	res = {}

	for (global_params, items1) in dominating_data.items():
		for (source_period, items2) in items1.items():
			for (safety_factor, items3) in items2.items():
				for ((algo_name, new_local_params), results) in items3.items():

					local_params = tuple(np.insert(new_local_params, safety_factor_indexes[algo_name], [safety_factor]))

					res.setdefault(algo_name, {}).setdefault(global_params, {}).setdefault(source_period, {})[local_params] = results

	return res


algorithm_names = ["protectionless_chen", "protectionless_ctp_chen", "phantom_walkabouts",
				   "phantom_chen", "ilprouting_chen", "adaptive_spr_notify_chen"]

new_global_parameters, res = all_results(algorithm_names)

#pprint(res)

dominating_data, dominated_data = filter_strictly_worse(res)

#pprint(dominated_data)

multiple_dominating_data = convert_dominating_to_individual(dominating_data)

pprint(multiple_dominating_data)
