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

	results_data = [transform_results_data(result.data, parameters_to_remove) for result in module_results]

	return results_data



res = all_results(["protectionless_chen", "protectionless_ctp_chen","phantom_walkabouts"])

pprint(res)
