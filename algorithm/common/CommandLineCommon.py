from __future__ import print_function
import os, sys

from data import results, latex
from data.table import fake_result
from data.util import recreate_dirtree, touch

class CLI(object):

    parameter_names = None

    def __init__(self, package):
        super(CLI, self).__init__()

        self.algorithm_module = __import__(package, globals(), locals(), ['object'], -1)

    @staticmethod
    def _get_args_for(args, name):
        name += "="
        return [arg[len(name):] for arg in args if arg.startswith(name)]

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

        thread_count = self._get_args_for(args, 'thread_count')
        if len(thread_count) == 1:
            driver.job_thread_count = int(thread_count[0])

        self._execute_runner(driver, self.algorithm_module.results_path, skip_completed_simulations=True)

    def _run_analyse(self, args):
        analyzer = self.algorithm_module.Analysis.Analyzer(self.algorithm_module.results_path)
        analyzer.run(self.algorithm_module.result_file)

    def _run_cluster(self, args):
        cluster_directory = os.path.join("cluster", self.algorithm_module.name)

        from data import cluster_manager

        cluster = cluster_manager.load(args)

        if 'build' in args:
            recreate_dirtree(cluster_directory)
            touch("{}/__init__.py".format(os.path.dirname(cluster_directory)))
            touch("{}/__init__.py".format(cluster_directory))

            self._execute_runner(cluster.builder(), cluster_directory, skip_completed_simulations=False)

        if 'copy' in args:
            cluster.copy_to()

        if 'submit' in args:
            emails_to_notify = self._get_args_for(args, 'notify')

            self._execute_runner(cluster.submitter(emails_to_notify), cluster_directory, skip_completed_simulations=False)

        if 'copy-back' in args:
            cluster.copy_back(self.algorithm_module.name)

        sys.exit(0)

    def _run_time_taken_table(self, args):
        result = results.Results(self.algorithm_module.result_file_path,
                                 parameters=self.parameter_names,
                                 results=('time taken', 'wall time', 'event count'))

        result_table = fake_result.ResultTable(result)

        self._create_table(self.algorithm_module.name + "-time-taken", result_table)

    def _run_detect_missing(self, args):
        result = results.Results(self.algorithm_module.result_file_path,
                                 parameters=self.parameter_names,
                                 results=('repeats',))

        for ((size, config, am, nm, cm), items1) in result.data.items():
            for (src_period, items2) in items1.items():
                for (params, all_results) in items2.items():

                    repeats_performed = all_results[result.result_names.index('repeats')]

                    repeats_missing = max(self.repeats - repeats_performed, 0)

                    # Number of repeats is below the target
                    if repeats_missing > 0:

                        print("performed={} missing={} ".format(repeats_performed, repeats_missing), end="")

                        parameter_values = [size, config, am, nm, cm, src_period] + list(params)
                        parameter_names = ['network size', 'configuration',
                                            'attacker model', 'noise model',
                                            'communication model', 'source period'
                                           ] + result.parameter_names

                        print(", ".join([n + "=" + str(v) for (n,v) in zip(parameter_names, parameter_values)]))
                        print()

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
