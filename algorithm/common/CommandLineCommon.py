from __future__ import print_function
import os, sys

from data import results, latex
from data.table import fake_result
from data.graph import heatmap
from data.util import recreate_dirtree, touch

class CLI(object):

    # Parameters that all simulations must have
    # The source period must come last
    global_parameter_names = ['network size', 'configuration',
                              'attacker model', 'noise model',
                              'communication model', 'distance', 'source period']

    # Parameters unique to each simulation
    # Classes that derive from this should assign this variable
    local_parameter_names = None

    def __init__(self, package):
        super(CLI, self).__init__()

        self.algorithm_module = __import__(package, globals(), locals(), ['object'], -1)

    def parameter_names(self):
        return tuple(list(self.global_parameter_names) + list(self.local_parameter_names))

    @staticmethod
    def _get_args_for(args, name):
        name += "="
        return [arg[len(name):] for arg in args if arg.startswith(name)]

    @staticmethod
    def _get_arg_for(args, name):
        found_args = CLI._get_args_for(args, name)
        if len(found_args) == 1:
            return found_args[0]
        else:
            raise RuntimeError("Only one value is expected for {}".format(name))

    @staticmethod
    def _create_table(name, result_table, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)

    def _execute_runner(self, driver, result_path, skip_completed_simulations):
        raise NotImplementedError()

    def _run_run(self, args):
        from data.run.driver import local as LocalDriver
        driver = LocalDriver.Runner()

        thread_count = self._get_arg_for(args, 'thread_count')
        driver.job_thread_count = int(thread_count)

        self._execute_runner(driver, self.algorithm_module.results_path, skip_completed_simulations=True)

    def _run_analyse(self, args):
        analyzer = self.algorithm_module.Analysis.Analyzer(self.algorithm_module.results_path)
        analyzer.run(self.algorithm_module.result_file)

    def _run_cluster(self, args):
        cluster_directory = os.path.join("cluster", self.algorithm_module.name)

        from data import cluster_manager

        cluster = cluster_manager.load(args)

        skip_complete = 'no-skip-complete' not in args

        if 'build' in args:
            recreate_dirtree(cluster_directory)
            touch("{}/__init__.py".format(os.path.dirname(cluster_directory)))
            touch("{}/__init__.py".format(cluster_directory))

            self._execute_runner(cluster.builder(), cluster_directory, skip_completed_simulations=skip_complete)

        if 'copy' in args:
            cluster.copy_to()

        if 'copy-result-summary' in args:
            cluster.copy_result_summary(self.algorithm_module.results_path, self.algorithm_module.result_file)

        if 'submit' in args:
            emails_to_notify = self._get_args_for(args, 'notify')

            if 'array' not in args:
                submitter = cluster.submitter(emails_to_notify)
            else:
                submitter = cluster.array_submitter(emails_to_notify)

            self._execute_runner(submitter, cluster_directory, skip_completed_simulations=skip_complete)

        if 'copy-back' in args:
            cluster.copy_back(self.algorithm_module.name)

        sys.exit(0)

    def _run_time_taken_table(self, args):
        result = results.Results(self.algorithm_module.result_file_path,
                                 parameters=self.local_parameter_names,
                                 results=('time taken', 'wall time', 'event count'))

        result_table = fake_result.ResultTable(result)

        self._create_table(self.algorithm_module.name + "-time-taken", result_table)

    def _run_detect_missing(self, args):
        # TODO: Extend this to also handle missing results files

        result = results.Results(self.algorithm_module.result_file_path,
                                 parameters=self.local_parameter_names,
                                 results=('repeats',))

        repeats = result.parameter_set()

        for (parameter_values, repeats_performed) in repeats.items():

            repeats_missing = max(self.repeats - repeats_performed, 0)

            # Number of repeats is below the target
            if repeats_missing > 0:

                print("performed={} missing={} ".format(repeats_performed, repeats_missing), end="")

                parameter_names = self.global_parameter_names + result.parameter_names

                print(", ".join([n + "=" + str(v) for (n,v) in zip(parameter_names, parameter_values)]))
                print()

    def _run_graph_heatmap(self, args):
        heatmap_results = ('sent heatmap', 'received heatmap')

        results_summary = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=heatmap_results)

        for name in heatmap_results:
            heatmap.Grapher(self.algorithm_module.graphs_path, results_summary, name).create()
            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name.replace(" ", "_"))
            ).run()


    def run(self, args):

        if 'cluster' in args:
            self._run_cluster(args)

        if 'run' in args:
            self._run_run(args)

        if 'analyse' in args:
            self._run_analyse(args)

        if 'time-taken-table' in args:
            self._run_time_taken_table(args)

        if 'detect-missing' in args:
            self._run_detect_missing(args)

        if 'graph-heatmap' in args:
            self._run_graph_heatmap(args)
