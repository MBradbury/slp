__all__ = ("Analysis", "Arguments", "CommandLine", "Metrics")

def _setup():
    import algorithm
    return algorithm._setup_algorithm_paths(__package__.split(".")[1])

(name, results_path, result_file, result_file_path, graphs_path) = _setup()


local_parameter_names = ('short walk length', 'long walk length', 'direction bias',
                         'order', 'short count', 'long count', 'wait before short')
