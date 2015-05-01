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
