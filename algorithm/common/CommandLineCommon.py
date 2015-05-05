import os, sys

from data.util import recreate_dirtree, touch

class CLI(object):
    def __init__(self, package):
        self.algorithm_module = __import__(package, globals(), locals(), ['object'], -1)

    def _execute_runner(self, driver, results_directory, skip_completed_simulations):
        raise NotImplementedError()

    def _run_run(self, args):
        from data.run.driver import local as LocalDriver
        self._execute_runner(LocalDriver.Runner(), self.algorithm_module.results_path, skip_completed_simulations=True)

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
            self._execute_runner(cluster.submitter(), cluster_directory, skip_completed_simulations=False)

        if 'copy-back' in args:
            cluster.copy_back(self.algorithm_module.name)

        sys.exit(0)

    def _run_time_taken_table(self, args):
        from data import results, latex
        from data.table import fake_result

        results = results.Results(self.algorithm_module.result_file_path,
            parameters=self.parameter_names,
            results=('wall time', 'event count'))

        result_table = fake_result.ResultTable(results)

        def create_table(name, param_filter=lambda x: True):
            filename = name + ".tex"

            with open(filename, 'w') as result_file:
                latex.print_header(result_file)
                result_table.write_tables(result_file, param_filter)
                latex.print_footer(result_file)

            latex.compile_document(filename)

        create_table(self.algorithm_module.name + "-time-taken")

    def run(self, args):

        if 'cluster' in args:
            self._run_cluster(args)

        if 'run' in args:
            self._run_run(args)

        if 'analyse' in args:
            self._run_analyse(args)

        if 'time-taken-table' in args:
            self._run_time_taken_table(args)
