import os, sys

from data.util import recreate_dirtree, touch

class CLI(object):
    def __init__(self):
        pass

    def _execute_runner(self, driver, results_directory, skip_completed_simulations):
        raise NotImplemented()

    def _run_run(self, args, algorithm_module):
        from data.run.driver import local as LocalDriver
        self._execute_runner(LocalDriver.Runner(), algorithm_module.results_path)

    def _run_analyse(self, args, algorithm_module):
        analyzer = algorithm_module.Analysis.Analyzer(algorithm_module.results_path)
        analyzer.run(algorithm_module.result_file)

    def _run_cluster(self, args, algorithm_name):
        cluster_directory = os.path.join("cluster", algorithm_name)

        from data import cluster_manager

        cluster = cluster_manager.load(args)

        if 'build' in args:
            recreate_dirtree(cluster_directory)
            touch("{}/__init__.py".format(os.path.dirname(cluster_directory)))
            touch("{}/__init__.py".format(cluster_directory))

            self._execute_runner(cluster.builder(), cluster_directory, False)

        if 'copy' in args:
            cluster.copy_to()

        if 'submit' in args:
            self._execute_runner(cluster.submitter(), cluster_directory, False)

        if 'copy-back' in args:
            cluster.copy_back(algorithm_name)

        sys.exit(0)
