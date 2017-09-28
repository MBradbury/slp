__all__ = ("Analysis", "Arguments", "CommandLine", "Metrics")

def _setup():
    import algorithm
    return algorithm._setup_algorithm_paths(__package__.split(".")[1])

(name, results_path, result_file, result_file_path, graphs_path) = _setup()

local_parameter_names = ('slot period', 'dissem period', 'genetic header')

def get_parameters_in_header(name):
    import os.path

    params = {}

    with open(os.path.join("algorithm", "slp_tdma_das_ga", "ga_headers", name), "r") as gh_file:
        for line in gh_file:
            if line.startswith("#define "):
                try:
                    name, value = line[len("#define "):].split(" ", 1)
                except ValueError:
                    continue

                params[name] = int(value)

    return params
