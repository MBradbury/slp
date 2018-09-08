__all__ = ("Analysis", "Arguments", "CommandLine", "Metrics")

def _setup():
    import algorithm
    return algorithm._setup_algorithm_paths(__package__.split(".")[1])

(name, results_path, result_file, result_file_path, graphs_path) = _setup()


import algorithm.adaptive_spr_notify

base_parameter_names = algorithm.adaptive_spr_notify.local_parameter_names
extra_parameter_names = ('lpl local wakeup', 'lpl remote wakeup', 'lpl delay after receive', 'lpl max cca checks')
local_parameter_names = base_parameter_names + extra_parameter_names
