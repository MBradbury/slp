from __future__ import print_function, division

import argparse
import datetime
import importlib
import os
import sys

import simulator.common

import simulator.Configuration as Configuration

from data import results, latex
from data.table import safety_period, fake_result
from data.graph import heatmap, summary
from data.util import recreate_dirtree, touch

class CLI(object):

    global_parameter_names = simulator.common.global_parameter_names

    # Parameters unique to each simulation
    # Classes that derive from this should assign this variable
    local_parameter_names = None

    def __init__(self, package, safety_period_result_path=None, custom_run_simulation_class=None):
        super(CLI, self).__init__()

        self.algorithm_module = importlib.import_module(package)
        self.algorithm_module.Analysis = importlib.import_module("{}.Analysis".format(package))

        self.safety_period_result_path = safety_period_result_path

        self.custom_run_simulation_class = custom_run_simulation_class

        try:
            self.algorithm_module.Parameters = importlib.import_module("{}.Parameters".format(package))
        except ImportError:
            print("Failed to import Parameters, have you made sure to copy Parameters.py.sample to Parameters.py and then edit it?")

        parser = argparse.ArgumentParser(add_help=True)
        subparsers = parser.add_subparsers(title="mode", dest="mode")

        ###

        subparser = subparsers.add_parser("cluster")
        subparser.add_argument("name", type=str)

        cluster_subparsers = subparser.add_subparsers(title="cluster mode", dest="cluster_mode")

        subparser = cluster_subparsers.add_parser("build", help="Build the binaries used to run jobs on the cluster. One set of binaries will be created per parameter combination you request.")
        subparser.add_argument("--no-skip-complete", action="store_true")

        subparser = cluster_subparsers.add_parser("copy", help="Copy the built binaries for this algorithm to the cluster.")
        subparser = cluster_subparsers.add_parser("copy-result-summary", help="Copy the result summary for this algorithm obtained by using the 'analyse' command to the cluster.")
        subparser = cluster_subparsers.add_parser("copy-parameters", help="Copy this algorithm's Parameters.py file to the cluster.")
        subparser = cluster_subparsers.add_parser("submit", help="Use this command to submit the cluster jobs. Run this on the cluster.")
        subparser.add_argument("--array", action="store_true")
        subparser.add_argument("--notify", nargs="*")
        subparser.add_argument("--no-skip-complete", action="store_true")

        subparser = cluster_subparsers.add_parser("copy-back")

        ###

        subparser = subparsers.add_parser("testbed")
        subparser.add_argument("name", type=str)

        testbed_subparsers = subparser.add_subparsers(title="testbed mode", dest="testbed_mode")

        subparser = testbed_subparsers.add_parser("build")
        subparser.add_argument("--platform", type=str, default=None)

        ###

        subparser = subparsers.add_parser("run")
        subparser.add_argument("--thread-count", type=int, default=None)
        subparser.add_argument("--no-skip-complete", action="store_true")

        ###

        subparser = subparsers.add_parser("analyse")
        subparser.add_argument("--thread-count", type=int, default=None)
        subparser.add_argument("--headers-to-skip", nargs="*", metavar="H", help="The headers you want to skip analysis of.")

        ###

        subparser = subparsers.add_parser("time-taken-table")
        subparser = subparsers.add_parser("detect-missing")
        subparser = subparsers.add_parser("graph-heatmap")

        ###

        subparser = subparsers.add_parser("per-parameter-grapher")
        subparser.add_argument("--grapher", required=True)
        subparser.add_argument("--metric-name", required=True)

        subparser.add_argument("--without-converters", action="store_true", default=False)
        subparser.add_argument("--without-normalised", action="store_true", default=False)

        ###

        # Store any of the parsers that we need
        self._parser = parser
        self._subparsers = subparsers

    def parameter_names(self):
        return tuple(list(self.global_parameter_names) + list(self.local_parameter_names))

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

    def time_taken_to_safety_period(self, time_taken, first_normal_sent_time):
        return time_taken - first_normal_sent_time

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        if driver.mode() == "TESTBED":
            from data.run.common import RunTestbedCommon as RunSimulations
        else:
            # Time for something very crazy...
            # Some simulations require a safety period that varies depending on
            # the arguments to the simulation.
            #
            # So this custom RunSimulationsCommon class gets overridden and provided.
            if self.custom_run_simulation_class is None:
                from data.run.common import RunSimulationsCommon as RunSimulations
            else:
                RunSimulations = self.custom_run_simulation_class

        if self.safety_period_result_path is not None:
            if self.safety_period_result_path is True:
                safety_periods = True
            else:
                safety_period_table_generator = safety_period.TableGenerator(self.safety_period_result_path, self.time_taken_to_safety_period)
                safety_periods = safety_period_table_generator.safety_periods()
        else:
            safety_periods = None

        runner = RunSimulations(
            driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations,
            safety_periods=safety_periods
        )

        runner.run(self.algorithm_module.Parameters.repeats, self.parameter_names(), self._argument_product(), self._time_estimater)

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
            # Getting the configuration here with "topology" is fine, as we are only finding the number of sources.
            configuration = Configuration.create_specific(args[configuration_index],
                                                          args[size_index],
                                                          args[distance_index],
                                                          "topology",
                                                          None)
            num_sources = len(configuration.source_ids)

            source_period = args[source_period_index] * num_sources
            return args[:source_period_index] + (source_period,) + args[source_period_index+1:]

        return [process(*args) for args in argument_product]

    def _time_estimater(self, args, **kwargs):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        size = args['network size']
        if size == 11:
            return datetime.timedelta(hours=9)
        elif size == 15:
            return datetime.timedelta(hours=21)
        elif size == 21:
            return datetime.timedelta(hours=42)
        elif size == 25:
            return datetime.timedelta(hours=71)
        else:
            raise RuntimeError("No time estimate for network sizes other than 11, 15, 21 or 25")

    def _run_run(self, args):
        from data.run.driver import local as LocalDriver
        driver = LocalDriver.Runner()

        try:
            driver.job_thread_count = int(args.thread_count)
        except TypeError:
            # None tells the runner to use the default
            driver.job_thread_count = None

        skip_complete = not args.no_skip_complete

        self._execute_runner(driver, self.algorithm_module.results_path, skip_completed_simulations=skip_complete)

    def _run_analyse(self, args):
        analyzer = self.algorithm_module.Analysis.Analyzer(self.algorithm_module.results_path)
        analyzer.run(self.algorithm_module.result_file, args.thread_count, headers_to_skip=args.headers_to_skip)

    def _get_emails_to_notify(self, args):
        """Gets the emails that a cluster job should notify after finishing.
        This can be specified by using the "notify" parameter when submitting,
        or by setting the SLP_NOTIFY_EMAILS environment variable."""
        
        emails_to_notify = args.notify

        if emails_to_notify is None:
            emails_to_notify = []

        emails_to_notify_env = os.getenv("SLP_NOTIFY_EMAILS")
        if emails_to_notify_env:
            emails_to_notify.extend(emails_to_notify_env.split(","))

        return emails_to_notify

    def _run_cluster(self, args):
        cluster_directory = os.path.join("cluster", self.algorithm_module.name)

        import data.cluster
        from data import submodule_loader

        cluster = submodule_loader.load(data.cluster, args.name)

        if 'build' == args.cluster_mode:
            print("Removing existing cluster directory and creating a new one")
            recreate_dirtree(cluster_directory)
            touch("{}/__init__.py".format(os.path.dirname(cluster_directory)))
            touch("{}/__init__.py".format(cluster_directory))

            skip_complete = not args.no_skip_complete

            self._execute_runner(cluster.builder(), cluster_directory, skip_completed_simulations=skip_complete)

        elif 'copy' == args.cluster_mode:
            cluster.copy_to()

        elif 'copy-result-summary' == args.cluster_mode:
            cluster.copy_file(self.algorithm_module.results_path, self.algorithm_module.result_file)

        elif 'copy-parameters' == args.cluster_mode:
            cluster.copy_file(os.path.join('algorithm', self.algorithm_module.name), 'Parameters.py')

        elif 'submit' == args.cluster_mode:
            emails_to_notify = self._get_emails_to_notify(args)

            if args.array:
                submitter = cluster.array_submitter(emails_to_notify)
            else:
                submitter = cluster.submitter(emails_to_notify)

            skip_complete = not args.no_skip_complete

            self._execute_runner(submitter, cluster_directory, skip_completed_simulations=skip_complete)

        elif 'copy-back' == args.cluster_mode:
            cluster.copy_back(self.algorithm_module.name)

        sys.exit(0)

    def _run_testbed(self, args):
        testbed_directory = os.path.join("testbed", self.algorithm_module.name)

        import data.testbed
        from data import submodule_loader

        testbed = submodule_loader.load(data.testbed, args.name)

        if 'build' == args.testbed_mode:
            from data.run.driver.testbed_builder import Runner as Builder

            print("Removing existing testbed directory and creating a new one")
            recreate_dirtree(testbed_directory)

            self._execute_runner(Builder(testbed, platform=args.platform), testbed_directory, skip_completed_simulations=False)

        sys.exit(0)

    def _run_time_taken_table(self, args):
        result = results.Results(self.algorithm_module.result_file_path,
                                 parameters=self.local_parameter_names,
                                 results=('time taken', 'wall time', 'event count', 'repeats'))

        result_table = fake_result.ResultTable(result)

        self._create_table(self.algorithm_module.name + "-time-taken", result_table)

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

            repeats_missing = max(self.algorithm_module.Parameters.repeats - repeats_performed, 0)

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

    def _run_per_parameter_grapher(self, args):
        import data.graph
        from data import submodule_loader

        graph_type = submodule_loader.load(data.graph, args.grapher)

        analyzer = self.algorithm_module.Analysis.Analyzer(self.algorithm_module.results_path)

        grapher = graph_type.Grapher(
            os.path.join(self.algorithm_module.graphs_path, args.grapher),
            args.metric_name,
            self.parameter_names()
        )

        grapher.xaxis_label = args.metric_name

        grapher.create(analyzer,
                       with_converters=not args.without_converters,
                       with_normalised=not args.without_normalised
        )

        summary.GraphSummary(
            os.path.join(self.algorithm_module.graphs_path, args.grapher),
            '{}-{}'.format(self.algorithm_module.name, args.grapher)
        ).run()


    def run(self, args):
        args = self._parser.parse_args(args)

        if 'cluster' == args.mode:
            self._run_cluster(args)

        elif 'testbed' == args.mode:
            self._run_testbed(args)

        elif 'run' == args.mode:
            self._run_run(args)

        elif 'analyse' == args.mode:
            self._run_analyse(args)

        elif 'time-taken-table' == args.mode:
            self._run_time_taken_table(args)

        elif 'detect-missing' == args.mode:
            self._run_detect_missing(args)

        elif 'graph-heatmap' == args.mode:
            self._run_graph_heatmap(args)

        elif 'per-parameter-grapher' == args.mode:
            self._run_per_parameter_grapher(args)

        return args
