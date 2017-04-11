from __future__ import print_function, division

import argparse
from collections import defaultdict
from datetime import timedelta
import functools
import importlib
import itertools
import math
import os
import subprocess
import sys

import algorithm

import simulator.common
import simulator.sim
import simulator.Configuration as Configuration

from data import results, latex, submodule_loader
from data.run.common import MissingSafetyPeriodError

import data.clusters as clusters
import data.cycle_accurate
import data.testbed

from data.graph import heatmap, summary

from data.table import safety_period, fake_result
from data.table.data_formatter import TableDataFormatter

from data.util import recreate_dirtree, touch, scalar_extractor

class CLI(object):

    global_parameter_names = simulator.common.global_parameter_names

    def __init__(self, package, safety_period_result_path=None, custom_run_simulation_class=None, safety_period_equivalence=None):
        super(CLI, self).__init__()

        self.algorithm_module = importlib.import_module(package)
        self.algorithm_module.Analysis = importlib.import_module("{}.Analysis".format(package))

        self.safety_period_result_path = safety_period_result_path
        self.custom_run_simulation_class = custom_run_simulation_class

        self.safety_period_equivalence = safety_period_equivalence

        # Make sure that local_parameter_names is a tuple
        # People have run into issues where they used ('<name>') instead of ('<name>',)
        if not isinstance(self.algorithm_module.local_parameter_names, tuple):
            raise RuntimeError("self.algorithm_module.local_parameter_names must be a tuple! If there is only one element, have your forgotten the comma?")

        try:
            self.algorithm_module.Parameters = importlib.import_module("{}.Parameters".format(package))
        except ImportError:
            print("Failed to import Parameters. Have you made sure to copy Parameters.py.sample to Parameters.py and then edit it?")

        self._argument_handlers = {}

        self._parser = argparse.ArgumentParser(add_help=True)
        self._subparsers = self._parser.add_subparsers(title="mode", dest="mode")

        ###

        subparser = self._add_argument("cluster", self._run_cluster)
        subparser.add_argument("name", type=str, choices=clusters.available_names(), help="This is the name of the cluster")

        cluster_subparsers = subparser.add_subparsers(title="cluster mode", dest="cluster_mode")

        subparser = cluster_subparsers.add_parser("build", help="Build the binaries used to run jobs on the cluster. One set of binaries will be created per parameter combination you request.")
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--no-skip-complete", action="store_true")

        subparser = cluster_subparsers.add_parser("copy", help="Copy the built binaries for this algorithm to the cluster.")
        subparser.add_argument("--user", type=str, default=None, required=False, help="Override the username being guessed.")

        subparser = cluster_subparsers.add_parser("copy-result-summary", help="Copy the result summary for this algorithm obtained by using the 'analyse' command to the cluster.")
        subparser.add_argument("--user", type=str, default=None, required=False, help="Override the username being guessed.")

        subparser = cluster_subparsers.add_parser("copy-parameters", help="Copy this algorithm's Parameters.py file to the cluster.")
        subparser.add_argument("--user", type=str, default=None, required=False, help="Override the username being guessed.")

        subparser = cluster_subparsers.add_parser("submit", help="Use this command to submit the cluster jobs. Run this on the cluster.")
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--array", action="store_true", help="Submit multiple arrays jobs (experimental).")
        subparser.add_argument("--notify", nargs="*", help="A list of email's to send a message to when jobs finish. You can also specify these via the SLP_NOTIFY_EMAILS environment variable.")
        subparser.add_argument("--no-skip-complete", action="store_true", help="When specified the results file will not be read to check how many results still need to be performed. Instead as many repeats specified in the Parameters.py will be attempted.")

        subparser = cluster_subparsers.add_parser("copy-back", help="Copies the results off the cluster. WARNING: This will overwrite files in the algorithm's results directory with the same name.")
        subparser.add_argument("--user", type=str, default=None, required=False, help="Override the username being guessed.")

        ###

        subparser = self._add_argument("testbed", self._run_testbed)
        subparser.add_argument("name", type=str, choices=submodule_loader.list_available(data.testbed), help="This is the name of the testbed")

        testbed_subparsers = subparser.add_subparsers(title="testbed mode", dest="testbed_mode")

        subparser = testbed_subparsers.add_parser("build", help="Build the binaries used to run jobs on the testbed. One set of binaries will be created per parameter combination you request.")
        subparser.add_argument("--platform", type=str, default=None)
        subparser.add_argument("-g", "--generate-per-node-id-binary", default=False, action="store_true", help="Also create a per node id binary that can be used in deployment")

        subparser = testbed_subparsers.add_parser("submit", help="Use this command to submit the testbed jobs. Run this on your machine.")
        subparser.add_argument("--no-skip-complete", action="store_true", help="When specified the results file will not be read to check how many results still need to be performed. Instead as many repeats specified in the Parameters.py will be attempted.")


        ###

        subparser = self._add_argument("cycle_accurate", self._run_cycle_accurate)
        subparser.add_argument("name", type=str, choices=submodule_loader.list_available(data.cycle_accurate), help="This is the name of the cycle accurate simulator")

        cycleaccurate_subparsers = subparser.add_subparsers(title="cycle accurate mode", dest="cycle_accurate_mode")

        subparser = cycleaccurate_subparsers.add_parser("build", help="Build the binaries used to run jobs on the cycle accurate simulator. One set of binaries will be created per parameter combination you request.")
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--platform", type=str, default=None)
        subparser.add_argument("--max-buffer-size", type=int, default=256)

        ###

        subparser = self._add_argument("run", self._run_run, help="Run the parameters combination specified in Parameters.py on this local machine.")
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--thread-count", type=int, default=None)
        subparser.add_argument("--no-skip-complete", action="store_true")

        ###

        subparser = self._add_argument("analyse", self._run_analyse, help="Analyse the results of this algorithm.")
        subparser.add_argument("--thread-count", type=int, default=None)
        subparser.add_argument("-S", "--headers-to-skip", nargs="*", metavar="H", help="The headers you want to skip analysis of.")
        subparser.add_argument("-K", "--keep-if-hit-upper-time-bound", action="store_true", default=False, help="Specify this flag if you wish to keep results that hit the upper time bound.")

        ###

        if safety_period_result_path is not None:            
            if isinstance(safety_period_result_path, bool):
                pass
            else:
                subparser = self._add_argument("safety-table", self._run_safety_table, help="Output protectionless information along with the safety period to be used for those parameter combinations.")
                subparser.add_argument("--show-stddev", action="store_true")

        subparser = self._add_argument("time-taken-table", self._run_time_taken_table, help="Creates a table showing how long simulations took in real and virtual time.")
        subparser.add_argument("--show-stddev", action="store_true")
        subparser.add_argument("--show", action="store_true", default=False)

        subparser = self._add_argument("error-table", self._run_error_table, help="Creates a table showing the number of simulations in which an error occurred.")
        subparser.add_argument("--show", action="store_true", default=False)

        subparser = self._add_argument("detect-missing", self._run_detect_missing, help="List the parameter combinations that are missing results. This requires a filled in Parameters.py and for an 'analyse' to have been run.")

        subparser = self._add_argument("graph-heatmap", self._run_graph_heatmap, help="Graph the sent and received heatmaps.")

        ###

        subparser = self._add_argument("per-parameter-grapher", self._run_per_parameter_grapher)
        subparser.add_argument("--grapher", required=True)
        subparser.add_argument("--metric-name", required=True)
        subparser.add_argument("--show", action="store_true", default=False)

        subparser.add_argument("--without-converters", action="store_true", default=False)
        subparser.add_argument("--without-normalised", action="store_true", default=False)

        ###

        subparser = self._add_argument('historical-time-estimator', self._run_historical_time_estimator)
        subparser.add_argument("--key", nargs="+", metavar="P", default=('network size', 'source period'))

        ###

    def _add_argument(self, name, fn, **kwargs):
        self._argument_handlers[name] = fn
        return self._subparsers.add_parser(name, **kwargs)

    def parameter_names(self):
        return self.global_parameter_names + self.algorithm_module.local_parameter_names

    @staticmethod
    def _create_table(name, result_table, directory="results", param_filter=lambda x: True, orientation='portrait', show=False):
        filename = os.path.join(directory, name + ".tex")

        with open(filename, 'w') as result_file:
            latex.print_header(result_file, orientation=orientation)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        filename_pdf = latex.compile_document(filename)

        if show:
            subprocess.call(["xdg-open", filename_pdf])

    def _create_results_table(self, parameters, **kwargs):
        res = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=parameters)

        result_table = fake_result.ResultTable(res)

        self._create_table(self.algorithm_module.name + "-results", result_table, **kwargs)


    def _create_versus_graph(self, graph_parameters, varying,
                             custom_yaxis_range_max=None,
                             source_period_normalisation=None, network_size_normalisation=None, results_filter=None,
                             yextractor=scalar_extractor, xextractor=None,
                             **kwargs):
        from data.graph import versus

        algo_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation=source_period_normalisation,
            network_size_normalisation=network_size_normalisation,
            results_filter=results_filter)

        for ((xaxis, xaxis_units), (vary, vary_units)) in varying:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-{}-w-{}'.format(xaxis, yaxis, vary).replace(" ", "_")

                g = versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis=xaxis, yaxis=yaxis, vary=vary,
                    yextractor=yextractor, xextractor=xextractor)

                g.xaxis_label = xaxis.title()
                g.yaxis_label = yaxis_label
                g.vary_label = "/".join(x.title() for x in vary) if isinstance(vary, tuple) else vary.title()
                g.vary_prefix = vary_units
                g.key_position = key_position

                for (attr_name, attr_value) in kwargs.items():
                    if hasattr(g, attr_name):
                        setattr(g, attr_name, attr_value)

                if custom_yaxis_range_max is not None and yaxis in custom_yaxis_range_max:
                    g.yaxis_range_max = custom_yaxis_range_max[yaxis]

                if g.create(algo_results):
                    summary.GraphSummary(
                        os.path.join(self.algorithm_module.graphs_path, name),
                        os.path.join(algorithm.results_directory_name, 'v-{}-{}'.format(self.algorithm_module.name, name))
                    ).run()

    def _create_baseline_versus_graph(self, baseline_module, graph_parameters, varying,
                                      custom_yaxis_range_max=None,
                                      source_period_normalisation=None, network_size_normalisation=None, results_filter=None,
                                      **kwargs):
        from data.graph import baseline_versus

        algo_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation=source_period_normalisation,
            network_size_normalisation=network_size_normalisation,
            results_filter=results_filter)

        baseline_results = results.Results(
            baseline_module.result_file_path,
            parameters=baseline_module.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation=source_period_normalisation,
            network_size_normalisation=network_size_normalisation,
            results_filter=results_filter)

        for ((xaxis, xaxis_units), (vary, vary_units)) in varying:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = 'baseline-{}-v-{}-w-{}'.format(xaxis, yaxis, vary).replace(" ", "_")

                g = baseline_versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis=xaxis, yaxis=yaxis, vary=vary,
                    yextractor=scalar_extractor)

                g.xaxis_label = xaxis.title()
                g.yaxis_label = yaxis_label
                g.vary_label = vary.title()
                g.vary_prefix = vary_units
                g.key_position = key_position

                for (attr_name, attr_value) in kwargs.items():
                    setattr(g, attr_name, attr_value)

                if custom_yaxis_range_max is not None and yaxis in custom_yaxis_range_max:
                    g.yaxis_range_max = custom_yaxis_range_max[yaxis]

                if g.create(algo_results, baseline_results):
                    summary.GraphSummary(
                        os.path.join(self.algorithm_module.graphs_path, name),
                        os.path.join(algorithm.results_directory_name, 'bl-{}_{}-{}'.format(self.algorithm_module.name, baseline_module.name, name))
                    ).run()

    def _create_min_max_versus_graph(self, comparison_modules, baseline_module, graph_parameters, varying,
                                     custom_yaxis_range_max=None,
                                     source_period_normalisation=None, network_size_normalisation=None, results_filter=None,
                                     **kwargs):
        from data.graph import min_max_versus

        algo_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation=source_period_normalisation,
            network_size_normalisation=network_size_normalisation,
            results_filter=results_filter)

        all_comparion_results = [
            results.Results(
                comparion_module.result_file_path,
                parameters=comparion_module.local_parameter_names,
                results=tuple(graph_parameters.keys()),
                source_period_normalisation=source_period_normalisation,
                network_size_normalisation=network_size_normalisation,
                results_filter=results_filter)

            for comparion_module in comparison_modules
        ]

        if baseline_module is not None:
            baseline_results = results.Results(
                baseline_module.result_file_path,
                parameters=baseline_module.local_parameter_names,
                results=tuple(graph_parameters.keys()))
        else:
            baseline_results = None

        for ((xaxis, xaxis_units), (vary, vary_units)) in varying:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-{}-w-{}'.format(xaxis, yaxis, vary).replace(" ", "_")

                g = min_max_versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis=xaxis, yaxis=yaxis, vary=vary,
                    yextractor=scalar_extractor)

                g.xaxis_label = xaxis.title()
                g.yaxis_label = yaxis_label
                g.vary_label = vary.title()
                g.vary_prefix = vary_units
                g.key_position = key_position

                for (attr_name, attr_value) in kwargs.items():
                    setattr(g, attr_name, attr_value)

                if custom_yaxis_range_max is not None and yaxis in custom_yaxis_range_max:
                    g.yaxis_range_max = custom_yaxis_range_max[yaxis]

                if g.create(all_comparion_results, algo_results, baseline_results=baseline_results):
                    summary.GraphSummary(
                        os.path.join(self.algorithm_module.graphs_path, name),
                        os.path.join(algorithm.results_directory_name, 'mmv-{}_{}-{}'.format(self.algorithm_module.name, "_".join(mod.name for mod in comparison_modules), name))
                    ).run()

    def _argument_product(self):
        """Produces the product of the arguments specified in a Parameters.py file of the self.algorithm_module.

        Algorithms that do anything special will need to implement this themselves.
        """
        # Lets do our best to implement an argument product that we can expect an algorithm to need.

        parameters = self.algorithm_module.Parameters

        product_argument = []

        # Some arguments are non-plural
        non_plural_global_parameters = ["distance", "latest node start time"]

        # Some arguments are not properly named
        synonyms = {
            "network size": "sizes"
        }

        def _get_global_plural_name(global_name):
            plural_name = synonyms.get(global_name, None)
            if plural_name is not None:
                return plural_name
            return global_name.replace(" ", "_") + "s"

        # First lets sort out the global parameters
        for global_name in self.global_parameter_names:
            if global_name in non_plural_global_parameters:
                product_argument.append([getattr(parameters, global_name.replace(" ", "_"))])
            else:
                product_argument.append(getattr(parameters, _get_global_plural_name(global_name)))

        # Now lets process the algorithm specific parameters
        for local_name in self.algorithm_module.local_parameter_names:
            product_argument.append(getattr(parameters, local_name.replace(" ", "_") + "s"))

        argument_product = itertools.product(*product_argument)

        # Factor in the number of sources when selecting the source period.
        # This is done so that regardless of the number of sources the overall
        # network's normal message generation rate is the same.
        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product

    def time_after_first_normal_to_safety_period(self, time_after_first_normal):
        return time_after_first_normal

    def _execute_runner(self, sim, driver, result_path, time_estimator=None, skip_completed_simulations=True):
        if driver.mode() == "TESTBED":
            from data.run.common import RunTestbedCommon as RunSimulations
        elif driver.mode() == "CYCLEACCURATE":
            from data.run.common import RunCycleAccurateCommon as RunSimulations
            RunSimulations = functools.partial(RunSimulations, sim)
        else:
            # Time for something very crazy...
            # Some simulations require a safety period that varies depending on
            # the arguments to the simulation.
            #
            # So this custom RunSimulationsCommon class gets overridden and provided.
            if self.custom_run_simulation_class is None:
                from data.run.common import RunSimulationsCommon as RunSimulations
                RunSimulations = functools.partial(RunSimulations, sim)
            else:
                RunSimulations = functools.partial(self.custom_run_simulation_class, sim)

        if self.safety_period_result_path is True:
            safety_periods = True
        elif self.safety_period_result_path is None:
            safety_periods = None
        else:
            safety_period_table_generator = safety_period.TableGenerator(
                self.safety_period_result_path,
                self.time_after_first_normal_to_safety_period)
            
            safety_periods = safety_period_table_generator.safety_periods()

        runner = RunSimulations(
            driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations,
            safety_periods=safety_periods,
            safety_period_equivalence=self.safety_period_equivalence
        )

        argument_product = self._argument_product()

        argument_product_duplicates = _duplicates_in_iterable(argument_product)

        if len(argument_product_duplicates) > 0:
            from pprint import pprint
            print("There are duplicates in your argument product, check your Parameters.py file.")
            print("The following parameters have duplicates of them:")
            pprint(argument_product_duplicates)
            raise RuntimeError("There are duplicates in your argument product, check your Parameters.py file.")

        try:
            runner.run(self.algorithm_module.Parameters.repeats,
                       self.parameter_names(),
                       argument_product,
                       time_estimator)
        except MissingSafetyPeriodError as ex:
            from pprint import pprint
            import traceback
            print(traceback.format_exc())
            print("Available safety periods:")
            pprint(ex.safety_periods)

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

    def _cluster_time_estimator(self, args, **kwargs):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        size = args['network size']
        if size == 11:
            return timedelta(hours=9)
        elif size == 15:
            return timedelta(hours=21)
        elif size == 21:
            return timedelta(hours=42)
        elif size == 25:
            return timedelta(hours=71)
        else:
            raise RuntimeError("No time estimate for network sizes other than 11, 15, 21 or 25")

    def _cluster_time_estimator_from_historical(self, args, kwargs, historical_key_names, historical, allowance=0.2, max_time=None):
        key = tuple(args[name] for name in historical_key_names)

        try:
            try:
                hist_time = historical[key]
            except KeyError:
                # Try with every item as a string instead
                key = tuple(str(x) for x in key)
                hist_time = historical[key]

            job_size = kwargs["job_size"]
            thread_count = kwargs["thread_count"]

            total_time = hist_time * job_size
            time_per_proc = total_time // thread_count
            time_per_proc_with_allowance = timedelta(seconds=time_per_proc.total_seconds() * (1 + allowance))

            # To count for python process start up and shutdown
            extra_time_per_proc = timedelta(seconds=2)
            extra_time = (extra_time_per_proc * job_size) // thread_count

            calculated_time = time_per_proc_with_allowance + extra_time

            if max_time is not None:
                if calculated_time > max_time:
                    print("Warning: The estimated cluster time is {}, overriding this with the maximum {}".format(calculated_time, max_time))
                    calculated_time = max_time

            return calculated_time

        except KeyError:
            print("Unable to find historical time for {}, so using default time estimator.".format(key))
            return self._cluster_time_estimator(args, **kwargs)

    def _run_run(self, args):
        from data.run.driver import local as LocalDriver
        driver = LocalDriver.Runner()

        try:
            driver.job_thread_count = int(args.thread_count)
        except TypeError:
            # None tells the runner to use the default
            driver.job_thread_count = None

        skip_complete = not args.no_skip_complete

        self._execute_runner(args.sim, driver, self.algorithm_module.results_path,
                             time_estimator=None,
                             skip_completed_simulations=skip_complete)

    def _run_analyse(self, args):
        analyzer = self.algorithm_module.Analysis.Analyzer(self.algorithm_module.results_path)
        analyzer.run(self.algorithm_module.result_file,
                     nprocs=args.thread_count,
                     headers_to_skip=args.headers_to_skip,
                     keep_if_hit_upper_time_bound=args.keep_if_hit_upper_time_bound)

    def _run_safety_table(self, args):

        fmt = TableDataFormatter(convert_to_stddev=args.show_stddev)

        safety_period_table = safety_period.TableGenerator(self.safety_period_result_path, self.time_after_first_normal_to_safety_period, fmt)

        prod = itertools.product(simulator.common.available_noise_models(),
                                 simulator.common.available_communication_models())

        for (noise_model, comm_model) in prod:

            print("Writing results table for the {} noise model and {} communication model".format(noise_model, comm_model))

            filename = '{}-{}-{}-safety'.format(self.algorithm_module.name, noise_model, comm_model)

            self._create_table(filename, safety_period_table,
                               param_filter=lambda (cm, nm, am, fm, c, d, nido, lst): nm == noise_model and cm == comm_model)

    def _run_error_table(self, args):
        res = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=('dropped no sink delivery', 'dropped hit upper bound', 'dropped duplicates'))

        result_table = fake_result.ResultTable(res)

        self._create_table(self.algorithm_module.name + "-error-results", result_table, show=args.show)

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

        cluster = clusters.create(args.name)

        if 'build' == args.cluster_mode:
            print("Removing existing cluster directory and creating a new one")
            recreate_dirtree(cluster_directory)
            touch("{}/__init__.py".format(os.path.dirname(cluster_directory)))
            touch("{}/__init__.py".format(cluster_directory))

            skip_complete = not args.no_skip_complete

            self._execute_runner(args.sim, cluster.builder(), cluster_directory,
                                 time_estimator=None,
                                 skip_completed_simulations=skip_complete)

        elif 'copy' == args.cluster_mode:
            cluster.copy_to(self.algorithm_module.name, user=args.user)

        elif 'copy-result-summary' == args.cluster_mode:
            cluster.copy_file(self.algorithm_module.results_path, self.algorithm_module.result_file, user=args.user)

        elif 'copy-parameters' == args.cluster_mode:
            cluster.copy_file(os.path.join('algorithm', self.algorithm_module.name), 'Parameters.py', user=args.user)

        elif 'submit' == args.cluster_mode:
            emails_to_notify = self._get_emails_to_notify(args)

            if args.array:
                submitter = cluster.array_submitter(emails_to_notify)
            else:
                submitter = cluster.submitter(emails_to_notify)

            skip_complete = not args.no_skip_complete

            self._execute_runner(args.sim, submitter, cluster_directory,
                                 time_estimator=self._cluster_time_estimator,
                                 skip_completed_simulations=skip_complete)

        elif 'copy-back' == args.cluster_mode:
            cluster.copy_back(self.algorithm_module.name, user=args.user)

        else:
            raise RuntimeError("Unknown cluster mode {}".format(args.cluster_mode))

        sys.exit(0)

    def _run_testbed(self, args):
        testbed_directory = os.path.join("testbed", self.algorithm_module.name)

        testbed = submodule_loader.load(data.testbed, args.name)

        if 'build' == args.testbed_mode:
            from data.run.driver.testbed_builder import Runner as Builder

            print("Removing existing testbed directory and creating a new one")
            recreate_dirtree(testbed_directory)

            builder = Builder(
                testbed,
                platform=args.platform,
                generate_per_node_id_binary=args.generate_per_node_id_binary
            )

            self._execute_runner("real", builder, testbed_directory,
                                 time_estimator=None,
                                 skip_completed_simulations=False)

        elif 'submit' == args.testbed_mode:
            submitter = testbed.submitter()

            skip_complete = not args.no_skip_complete

            self._execute_runner("real", submitter, testbed_directory,
                                 time_estimator=None,
                                 skip_completed_simulations=skip_complete)

        sys.exit(0)

    def _run_cycle_accurate(self, args):
        cycle_accurate_directory = os.path.join("cycle_accurate", self.algorithm_module.name)

        cycle_accurate = submodule_loader.load(data.cycle_accurate, args.name)

        if 'build' == args.cycle_accurate_mode:
            from data.run.driver.cycle_accurate_builder import Runner as Builder

            print("Removing existing cycle accurate directory and creating a new one")
            recreate_dirtree(cycle_accurate_directory)

            builder = Builder(cycle_accurate, platform=args.platform, max_buffer_size=args.max_buffer_size)

            self._execute_runner(args.sim, builder, cycle_accurate_directory,
                                 time_estimator=None,
                                 skip_completed_simulations=False)

        sys.exit(0)

    def _run_time_taken_table(self, args):
        result = results.Results(self.algorithm_module.result_file_path,
                                 parameters=self.algorithm_module.local_parameter_names,
                                 results=('time taken', 'first normal sent time',
                                          'total wall time', 'wall time', 'event count',
                                          'repeats', 'captured', 'reached upper bound',
                                          'memory rss', 'memory vms'))

        fmt = TableDataFormatter(convert_to_stddev=args.show_stddev)

        result_table = fake_result.ResultTable(result, fmt)

        self._create_table(self.algorithm_module.name + "-time-taken", result_table, orientation="landscape", show=args.show)

    def _run_detect_missing(self, args):
        
        argument_product = {tuple(map(str, row)) for row in self._argument_product()}

        result = results.Results(self.algorithm_module.result_file_path,
                                 parameters=self.algorithm_module.local_parameter_names,
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
        heatmap_results = [
            header
            for header
            in self.algorithm_module.Analysis.Analyzer.results_header().keys()
            if header.endswith('heatmap')
        ]

        results_summary = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=heatmap_results)

        for name in heatmap_results:
            heatmap.Grapher(self.algorithm_module.graphs_path, results_summary, name).create()
            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name.replace(" ", "_")))
            ).run()

    def _run_per_parameter_grapher(self, args):
        import data.graph as data_graph

        graph_type = submodule_loader.load(data_graph, args.grapher)

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
            os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, args.grapher))
        ).run(show=args.show)

    def _run_historical_time_estimator(self, args):
        result = results.Results(self.algorithm_module.result_file_path,
                                 parameters=self.algorithm_module.local_parameter_names,
                                 results=('total wall time',))

        max_wall_times = defaultdict(float)

        # For each network size and source period find the maximum total wall time

        for (global_params, values1) in result.data.items():

            global_params = dict(zip(self.global_parameter_names, global_params))

            for (source_period, values2) in values1.items():

                source_period_params = {'source period': source_period}

                for (local_params, values3) in values2.items():

                    local_params = dict(zip(self.algorithm_module.local_parameter_names, local_params))

                    params = {}
                    params.update(global_params)
                    params.update(source_period_params)
                    params.update(local_params)

                    key = tuple(params[name] for name in args.key)

                    (total_wall_time, total_wall_time_stddev) = values3[0]

                    # Add in the deviation to ensure we consider the extreme cases
                    total_wall_time += total_wall_time_stddev

                    max_wall_times[key] = max(max_wall_times[key], total_wall_time)

        print("historical_key_names = {}".format(tuple(args.key)))
        print("historical = {")
        for key, value in sorted(max_wall_times.items(), key=lambda x: x[0]):
            print("    {}: timedelta(seconds={}),".format(key, int(math.ceil(value))))
        print("}")


    def run(self, args):
        args = self._parser.parse_args(args)

        self._argument_handlers[args.mode](args)

        return args


def _duplicates_in_iterable(iterable):
    seen = set()
    seen2 = set()
    seen_add = seen.add
    seen2_add = seen2.add
    for item in iterable:
        if item in seen:
            seen2_add(item)
        else:
            seen_add(item)
    return list(seen2)
