
import importlib
from os.path import join as os_path_join
import sys

results_directory_name = "results"
testbed_results_directory_name = "testbed_results"
graphs_directory_name = "Graphs"

def _setup_algorithm_paths(name):
    def results_path(sim_name):
        return os_path_join(results_directory_name, sim_name, name)

    result_file = f"{name}-results.csv"

    def result_file_path(sim_name):
        return os_path_join(results_path(sim_name), result_file)

    def graphs_path(sim_name):
        return os_path_join(results_path(sim_name), graphs_directory_name)

    return (name, results_path, result_file, result_file_path, graphs_path)

def import_algorithm(name, extras=None):
    import_name = name

    if "." not in import_name:
        import_name = f"algorithm.{import_name}"

    algorithm_module = importlib.import_module(import_name)

    if extras is not None:
        for extra in extras:
            if not hasattr(algorithm_module, extra):
                extra_module = importlib.import_module(f"{import_name}.{extra}")
                setattr(algorithm_module, extra, extra_module)

    return algorithm_module
