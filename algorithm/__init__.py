results_directory_name = "results"
graphs_directory_name = "Graphs"

def _setup_algorithm_paths(name):
	import os.path

	results_path = os.path.join(results_directory_name, name)

	result_file = "{}-results.csv".format(name)

	result_file_path = os.path.join(results_path, result_file)

	graphs_path = os.path.join(results_path, graphs_directory_name)

	return (name, results_path, result_file, result_file_path, graphs_path)
