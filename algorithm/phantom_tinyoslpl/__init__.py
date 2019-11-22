__all__ = ("Analysis", "Arguments", "CommandLine", "Metrics")

def _setup():
    import algorithm
    return algorithm._setup_algorithm_paths(__package__.split(".")[1])

(name, results_path, result_file, result_file_path, graphs_path) = _setup()

import algorithm.phantom

base_parameter_names = algorithm.phantom.local_parameter_names
local_parameter_names = base_parameter_names + ('lpl local wakeup', 'lpl remote wakeup', 'lpl delay after receive', 'lpl max cca checks')
