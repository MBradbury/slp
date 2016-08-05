from __future__ import print_function, division

import datetime
import importlib
import os
import sys

import simulator.common

import simulator.Configuration as Configuration

from data import results, latex
from data.table import fake_result
from data.graph import heatmap, summary
from data.util import recreate_dirtree, touch

class NoArgumentsFound(RuntimeError):
    def __init__(self, name):
        super(NoArgumentsFound, self).__init__("No arguments were found for {}".format(name))

class TooManyArgumentsFound(RuntimeError):
    def __init__(self, name):
        super(TooManyArgumentsFound, self).__init__("Only one value is expected for {}".format(name))

class CLI(object):

    global_parameter_names = simulator.common.global_parameter_names

    # Parameters unique to each simulation
    # Classes that derive from this should assign this variable
    local_parameter_names = None

    def __init__(self, package):
        super(CLI, self).__init__()

        self.algorithm_module = importlib.import_module(package)
        self.algorithm_module.Analysis = importlib.import_module("{}.Analysis".format(package))

        try:
            self.algorithm_module.Parameters = importlib.import_module("{}.Parameters".format(package))
        except ImportError:
            print("Failed to import Parameters, have you made sure to copy Parameters.py.sample to Parameters.py and then edit it?")

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
        elif len(found_args) == 0:
            raise NoArgumentsFound(name)
        else:
            raise TooManyArgumentsFound(name)

    @staticmethod
    def _create_table(name, result_table, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)

    def _argument_product(self):
        raise NotImplementedError()

    def _execute_runner(self, driver, result_path, skip_completed_simulations):
        raise NotImplementedError()

    def adjust_source_period_for_multi_source(self, argument_product):
        """For configurations with multiple sources, so that the network has the
        overall same message generation rate, the source period needs to be adjusted
        relative to the number of sources."""
        names = self.parameter_names()
        configuration_index = names.index('configuration')
        size_index = names.index('network size')
        distance_index = names.index('distance')
        source_period_index = names.index('source period')

        def process(*args):
            configuration = Configuration.create_specific(args[configuration_index], args[size_index], args[distance_index])
            num_sources = len(configuration.source_ids)
            source_period = args[source_period_index] * num_sources
            return args[:source_period_index] + (source_period,) + args[source_period_index+1:]

        return [process(*args) for args in argument_product]

    def _time_estimater(self, *args):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        names = self.parameter_names()
        size = args[names.index('network size')]
        if size == 11:
            return datetime.timedelta(hours=9)
        elif size == 15:
            return datetime.timedelta(hours=21)
        elif size == 21:
            return datetime.timedelta(hours=42)
        elif size == 25:
            return datetime.timedelta(hours=72)
        else:
            raise RuntimeError("No time estimate for network sizes other than 11, 15, 21 or 25")

    def _run_run(self, args):
        from data.run.driver import local as LocalDriver
        driver = LocalDriver.Runner()

        try:
            thread_count = self._get_arg_for(args, 'thread_count')
            driver.job_thread_count = int(thread_count)
        except NoArgumentsFound:
            # Use default
            driver.job_thread_count = None

        skip_complete = 'no-skip-complete' not in args

        self._execute_runner(driver, self.algorithm_module.results_path, skip_completed_simulations=skip_complete)

    def _run_analyse(self, args):
        analyzer = self.algorithm_module.Analysis.Analyzer(self.algorithm_module.results_path)
        analyzer.run(self.algorithm_module.result_file)

    def _get_emails_to_notify(self, args):
        """Gets the emails that a cluster job should notify after finishing.
        This can be specified by using the "notify" parameter when submitting,
        or by setting the SLP_NOTIFY_EMAILS environment variable."""
        
        emails_to_notify = self._get_args_for(args, 'notify')

        emails_to_notify_env = os.getenv("SLP_NOTIFY_EMAILS")
        if emails_to_notify_env:
            emails_to_notify.extend(emails_to_notify_env.split(","))

        return emails_to_notify

    def _run_cluster(self, args):
        cluster_directory = os.path.join("cluster", self.algorithm_module.name)

        from data import cluster_manager

        cluster = cluster_manager.load(args)

        skip_complete = 'no-skip-complete' not in args

        if 'build' in args:
            print("Removing existing cluster directory and creating a new one")
            recreate_dirtree(cluster_directory)
            touch("{}/__init__.py".format(os.path.dirname(cluster_directory)))
            touch("{}/__init__.py".format(cluster_directory))

            self._execute_runner(cluster.builder(), cluster_directory, skip_completed_simulations=skip_complete)

        if 'copy' in args:
            cluster.copy_to()

        if 'copy-result-summary' in args:
            cluster.copy_result_summary(self.algorithm_module.results_path, self.algorithm_module.result_file)

        if 'submit' in args:
            emails_to_notify = self._get_emails_to_notify(args)

            if 'array' not in args:
                submitter = cluster.submitter(emails_to_notify)
            else:
                submitter = cluster.array_submitter(emails_to_notify)

            self._execute_runner(submitter, cluster_directory, skip_completed_simulations=skip_complete)

        if 'copy-back' in args:
            cluster.copy_back(self.algorithm_module.name)

        sys.exit(0)

    def _run_testbed(self, args):

        from data import testbed_manager

        testbed = testbed_manager.load(args)

        testbed_directory = os.path.join("testbed", self.algorithm_module.name)

        if 'build' in args:
            from data.run.driver.testbed_builder import Runner as Builder

            print("Removing existing testbed directory and creating a new one")
            recreate_dirtree(testbed_directory)

            self._execute_runner(Builder(testbed), testbed_directory, skip_completed_simulations=False)

        sys.exit(0)

    def _run_time_taken_table(self, args):
        result = results.Results(self.algorithm_module.result_file_path,
                                 parameters=self.local_parameter_names,
                                 results=('time taken', 'wall time', 'event count', 'repeats'))

        result_table = fake_result.ResultTable(result)

        self._create_table(self.algorithm_module.name + "-time-taken", result_table)

    def _run_time_taken_boxplot(self, args):
        from data.graph import boxplot

        analyzer = self.algorithm_module.Analysis.Analyzer(self.algorithm_module.results_path)

        grapher = boxplot.Grapher(os.path.join(self.algorithm_module.graphs_path, "boxplot"), "TimeTaken", self.parameter_names())
        grapher.create(analyzer)

        summary.GraphSummary(
            os.path.join(self.algorithm_module.graphs_path, "boxplot"),
            '{}-{}'.format(self.algorithm_module.name, "boxplot")
        ).run()


    def _run_detect_missing(self, args):
        

        argument_product = {tuple(map(str, row)) for row in self._argument_product()}

        result = results.Results(self.algorithm_module.result_file_path,
                                 parameters=self.local_parameter_names,
                                 results=('repeats',))

        repeats = result.parameter_set()

        parameter_names = self.global_parameter_names + result.parameter_names

        print("Checking runs that were asked for, but not included...")

        for arguments in argument_product:
            if arguments not in repeats:
                print("missing ", end="")
                print(", ".join([n + "=" + str(v) for (n,v) in zip(parameter_names, arguments)]))
                print()

        print("Loading {} to check for missing runs...".format(self.algorithm_module.result_file_path))

        for (parameter_values, repeats_performed) in repeats.items():

            if parameter_values not in argument_product:
                continue

            repeats_missing = max(self.repeats - repeats_performed, 0)

            # Number of repeats is below the target
            if repeats_missing > 0:

                print("performed={} missing={} ".format(repeats_performed, repeats_missing), end="")

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

        if 'testbed' in args:
            self._run_testbed(args)

        if 'run' in args:
            self._run_run(args)

        if 'analyse' in args:
            self._run_analyse(args)

        if 'time-taken-table' in args:
            self._run_time_taken_table(args)

        if 'time-taken-boxplot' in args:
            self._run_time_taken_boxplot(args)

        if 'detect-missing' in args:
            self._run_detect_missing(args)

        if 'graph-heatmap' in args:
            self._run_graph_heatmap(args)
