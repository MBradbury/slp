
import importlib
from os.path import join as os_path_join

results_directory_name = "results"
testbed_results_directory_name = "testbed_results"
graphs_directory_name = "Graphs"

def _setup_algorithm_paths(name):
    results_path = os_path_join(results_directory_name, name)

    result_file = "{}-results.csv".format(name)

    result_file_path = os_path_join(results_path, result_file)

    graphs_path = os_path_join(results_path, graphs_directory_name)

    return (name, results_path, result_file, result_file_path, graphs_path)

def import_algorithm(name):
    algorithm_module = importlib.import_module("algorithm.{}".format(name))
    algorithm_module.Analysis = importlib.import_module("algorithm.{}.Analysis".format(name))

    return algorithm_module
