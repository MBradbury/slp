
import argparse
from collections import defaultdict
from datetime import timedelta
import fnmatch
import functools
import itertools
import math
import os
import re
import subprocess
import sys
import time
from types import ModuleType

from more_itertools import unique_everseen

import algorithm

from simulator import CommunicationModel, NoiseModel
import simulator.sim
import simulator.ArgumentsCommon as ArgumentsCommon
import simulator.Configuration as Configuration
import simulator.CoojaRadioModel as CoojaRadioModel

from data import results, latex, submodule_loader
from data.run.common import MissingSafetyPeriodError
from data.run.driver import platform_builder

import data.clusters as clusters
import data.cycle_accurate
import data.testbed

from data.graph import heatmap, summary

from data.table import safety_period, fake_result

from data.util import create_dirtree, recreate_dirtree, touch, scalar_extractor

# From: https://stackoverflow.com/questions/32954486/zip-iterators-asserting-for-equal-length-in-python
def zip_equal(*iterables):
    sentinel = object()
    for combo in itertools.zip_longest(*iterables, fillvalue=sentinel):
        if sentinel in combo:
            raise ValueError('Iterables have different lengths')
        yield combo

class CLI(object):

    def __init__(self, safety_period_module_name=None, custom_run_simulation_class=None, safety_period_equivalence=None):
        super(CLI, self).__init__()

        package = self.__module__.rsplit(".", 1)[0]

        try:
            self.algorithm_module = algorithm.import_algorithm(package, extras=["Analysis", "Parameters"])
        except ImportError:
            raise RuntimeError(f"Failed to import Parameters from {package}. Have you made sure to copy Parameters.py.sample to Parameters.py and then edit it?")

        self.safety_period_module_name = safety_period_module_name
        self.custom_run_simulation_class = custom_run_simulation_class

        self.safety_period_equivalence = safety_period_equivalence

        # Make sure that local_parameter_names is a tuple
        # People have run into issues where they used ('<name>') instead of ('<name>',)
        if not isinstance(self.algorithm_module.local_parameter_names, tuple):
            raise RuntimeError("self.algorithm_module.local_parameter_names must be a tuple! If there is only one element, have your forgotten the comma?")

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
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--user", type=str, default=None, required=False, help="Override the username being guessed.")

        subparser = cluster_subparsers.add_parser("copy-parameters", help="Copy this algorithm's Parameters.py file to the cluster.")
        subparser.add_argument("--user", type=str, default=None, required=False, help="Override the username being guessed.")

        subparser = cluster_subparsers.add_parser("submit", help="Use this command to submit the cluster jobs. Run this on the cluster.")
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--array", action="store_true", help="Submit multiple arrays jobs (experimental).")
        subparser.add_argument("--notify", nargs="*", help="A list of email's to send a message to when jobs finish. You can also specify these via the SLP_NOTIFY_EMAILS environment variable.")
        subparser.add_argument("--no-skip-complete", action="store_true", help="When specified the results file will not be read to check how many results still need to be performed. Instead as many repeats specified in the Parameters.py will be attempted.")
        subparser.add_argument("--dry-run", action="store_true", default=False)
        subparser.add_argument("--unhold", action="store_true", default=False, help="By default jobs are submitted in the held state. This argument will submit jobs in the unheld state.")
        subparser.add_argument("--min-repeats", type=ArgumentsCommon.ArgumentsCommon.type_positive_int, default=40, help="Minimum number of repeats to perform if an insufficient number has been performed thus far")

        subparser = cluster_subparsers.add_parser("copy-back", help="Copies the results off the cluster. WARNING: This will overwrite files in the algorithm's results directory with the same name.")
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--user", type=str, default=None, required=False, help="Override the username being guessed.")

        ###

        subparser = self._add_argument("testbed", self._run_testbed)
        subparser.add_argument("name", type=str, choices=submodule_loader.list_available(data.testbed), help="This is the name of the testbed")

        testbed_subparsers = subparser.add_subparsers(title="testbed mode", dest="testbed_mode")

        subparser = testbed_subparsers.add_parser("build", help="Build the binaries used to run jobs on the testbed. One set of binaries will be created per parameter combination you request.")
        subparser.add_argument("--platform", type=str, default=None)
        subparser.add_argument("-v", "--verbose", default=False, action="store_true", help="Produce verbose logging output from the testbed binaries")
        subparser.add_argument("--debug", default=False, action="store_true", help="Build debug binaries")

        subparser = testbed_subparsers.add_parser("submit", help="Use this command to submit the testbed jobs. Run this on your machine.")
        subparser.add_argument("--duration", type=str, help="How long you wish to run on the testbed for.", required=True)
        subparser.add_argument("--no-skip-complete", action="store_true", help="When specified the results file will not be read to check how many results still need to be performed. Instead as many repeats specified in the Parameters.py will be attempted.")
        subparser.add_argument("--dry-run", action="store_true", help="Do not actually submit, but check things would progress.")

        subparser = testbed_subparsers.add_parser("run", help="Process the testbed result files using the offline processor.")
        subparser.add_argument("--thread-count", type=int, default=None)
        ArgumentsCommon.OPTS["verbose"](subparser)
        ArgumentsCommon.OPTS["attacker model"](subparser)

        subparser = testbed_subparsers.add_parser("analyse", help="Analyse the testbed results of this algorithm.")
        subparser.add_argument("--thread-count", type=int, default=None)
        subparser.add_argument("-S", "--headers-to-skip", nargs="*", metavar="H", help="The headers you want to skip analysis of.")
        subparser.add_argument("-K", "--keep-if-hit-upper-time-bound", action="store_true", default=False, help="Specify this flag if you wish to keep results that hit the upper time bound.")
        subparser.add_argument("--flush", action="store_true", default=False, help="Flush any cached results.")

        ###

        subparser = self._add_argument("platform", self._run_platform)
        subparser.add_argument("name", type=str, choices=platform_builder.PLATFORM_TOOLS.keys(), help="This is the name of the platform")

        platform_subparsers = subparser.add_subparsers(title="platform mode", dest="platform_mode")

        subparser = platform_subparsers.add_parser("build", help="Build the binaries used to be deployed to nodes of a specific platform. One set of binaries will be created per parameter combination you request.")
        subparser.add_argument("-g", "--generate-per-node-id-binary", default=False, action="store_true")
        subparser.add_argument("--log-mode", choices=platform_builder.LOG_MODES.keys(), required=True)
        subparser.add_argument("-v", "--verbose", default=False, action="store_true", help="Produce verbose logging output from the testbed binaries")
        subparser.add_argument("--debug", default=False, action="store_true", help="Build debug binaries")

        ###

        subparser = self._add_argument("run", self._run_run, help="Run the parameters combination specified in Parameters.py on this local machine.")
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--thread-count", type=int, default=None)
        subparser.add_argument("--no-skip-complete", action="store_true")

        ###

        subparser = self._add_argument("analyse", self._run_analyse, help="Analyse the results of this algorithm.")
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--thread-count", type=int, default=None)
        subparser.add_argument("-S", "--headers-to-skip", nargs="*", metavar="H", help="The headers you want to skip analysis of.")
        subparser.add_argument("-K", "--keep-if-hit-upper-time-bound", action="store_true", default=False, help="Specify this flag if you wish to keep results that hit the upper time bound.")
        subparser.add_argument("--flush", action="store_true", default=False, help="Flush any cached results.")

        ###

        if safety_period_module_name is not None:
            # safety_period_module_name can be True
            # Only when it is a module name do we add the ability to run this command         
            if not isinstance(safety_period_module_name, bool):
                subparser = self._add_argument("safety-table", self._run_safety_table, help="Output protectionless information along with the safety period to be used for those parameter combinations.")
                subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
                subparser.add_argument("--show", action="store_true", default=False)
                subparser.add_argument("--testbed", type=str, choices=submodule_loader.list_available(data.testbed), default=None, help="Select the testbed to analyse. (Only if not analysing regular results.)")

        subparser = self._add_argument("time-taken-table", self._run_time_taken_table, help="Creates a table showing how long simulations took in real and virtual time.")
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--show", action="store_true", default=False)
        subparser.add_argument("--testbed", type=str, choices=submodule_loader.list_available(data.testbed), default=None, help="Select the testbed to analyse. (Only if not analysing regular results.)")

        subparser = self._add_argument("error-table", self._run_error_table, help="Creates a table showing the number of simulations in which an error occurred.")
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to check results for.")
        subparser.add_argument("--show", action="store_true", default=False)

        subparser = self._add_argument("convergence-table", self._run_convergence_table, help="Creates a table showing the results and error metrics.")
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to check results for.")
        subparser.add_argument("--show", action="store_true", default=False)

        subparser = self._add_argument("detect-missing", self._run_detect_missing, help="List the parameter combinations that are missing results. This requires a filled in Parameters.py and for an 'analyse' to have been run.")
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to check results for.")
        subparser.add_argument("--show-all", action="store_true", default=False)

        subparser = self._add_argument("graph-heatmap", self._run_graph_heatmap, help="Graph the sent and received heatmaps.")
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to check results for.")


        subparser = self._add_argument("graph-convergence", self._run_graph_convergence, help="Graph the mean of specific results as the simulation iterations progress.")
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to check results for.")
        subparser.add_argument("-H", "--headers", nargs="+", metavar="H", required=True)
        subparser.add_argument("--show", action="store_true", default=False)

        ###

        subparser = self._add_argument("per-parameter-grapher", self._run_per_parameter_grapher)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to check results for.")
        subparser.add_argument("--grapher", required=True)
        subparser.add_argument("--metric-name", required=True)
        subparser.add_argument("--show", action="store_true", default=False)

        subparser.add_argument("--without-converters", action="store_true", default=False)
        subparser.add_argument("--without-normalised", action="store_true", default=False)

        ###

        subparser = self._add_argument('historical-time-estimator', self._run_historical_time_estimator)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--key", nargs="+", metavar="P", default=('configuration', 'network size', 'source period'))

        ###

    def _add_argument(self, name, fn, **kwargs):
        self._argument_handlers[name] = fn
        return self._subparsers.add_parser(name, **kwargs)

    def parameter_names(self, sim):
        return sim.global_parameter_names + self.algorithm_module.local_parameter_names

    def _testbed_results_path(self, testbed, module=None):
        if module is None:
            module = self.algorithm_module

        testbed = testbed if isinstance(testbed, ModuleType) else submodule_loader.load(data.testbed, testbed)

        return os.path.join("results", "real", testbed.name(), module.name)

    def _testbed_results_file(self, testbed, module=None):
        if module is None:
            module = self.algorithm_module
        return os.path.join(self._testbed_results_path(testbed, module), module.result_file)

    def get_results_file_path(self, sim_name, testbed=None, module=None):
        if module is None:
            module = self.algorithm_module

        if testbed is not None:
            return self._testbed_results_file(testbed, module=module)
        else:
            return module.result_file_path(sim_name)

    def get_safety_period_result_path(self, sim_name, testbed=None):
        algo = algorithm.import_algorithm(self.safety_period_module_name)

        return self.get_results_file_path(sim_name, testbed=testbed, module=algo)


    @staticmethod
    def _create_table(name, result_table, directory="results", param_filter=lambda *args: True, orientation='portrait', show=False):
        filename = os.path.join(directory, name + ".tex")

        with open(filename, 'w') as result_file:
            latex.print_header(result_file, orientation=orientation)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        filename_pdf = latex.compile_document(filename)

        if show:
            subprocess.call(["xdg-open", filename_pdf])

    def _create_results_table(self, sim_name, parameters, results_filter=None,
                              fmt=None, hide_parameters=None, extractors=None,
                              resize_to_width=False, caption_values=None,
                              **kwargs):
        res = results.Results(
            sim_name, self.algorithm_module.result_file_path(sim_name),
            parameters=self.algorithm_module.local_parameter_names,
            results=parameters,
            results_filter=results_filter)

        result_table = fake_result.ResultTable(res, fmt=fmt,
            hide_parameters=hide_parameters, extractors=extractors, resize_to_width=resize_to_width, caption_values=caption_values)

        self._create_table(f"{self.algorithm_module.name}-{sim_name}-results", result_table, **kwargs)

    @classmethod
    def _shorter_name(cls, s):
        if isinstance(s, tuple):
            return cls._shorter_name("_".join(s))
        else:
            return "".join(x[0] for x in re.split(r"[\s,(]", str(s)) if x)

    def _create_versus_graph(self, sim_name, graph_parameters, varying, *,
                             custom_yaxis_range_max=None, custom_yaxis_range_min=None,
                             source_period_normalisation=None, network_size_normalisation=None, results_filter=None,
                             yextractor=scalar_extractor, xextractor=None, testbed=None,
                             **kwargs):
        from data.graph import versus

        algo_results = results.Results(
            sim_name, self.get_results_file_path(sim_name, testbed=testbed),
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation=source_period_normalisation,
            network_size_normalisation=network_size_normalisation,
            results_filter=results_filter)

        for ((xaxis, xaxis_units), (vary, vary_units)) in varying:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = f'{self._shorter_name(xaxis)}-v-{self._shorter_name(yaxis)}-w-{self._shorter_name(vary)}'

                if isinstance(yextractor, dict):
                    try:
                        yextractor_single = yextractor[yaxis]
                    except KeyError:
                        yextractor_single = scalar_extractor
                else:
                    yextractor_single = scalar_extractor

                g = versus.Grapher(
                    sim_name, self.algorithm_module.graphs_path(sim_name), name,
                    xaxis=xaxis, yaxis=yaxis, vary=vary,
                    yextractor=yextractor_single, xextractor=xextractor)

                g.xaxis_label = xaxis.title()
                g.yaxis_label = yaxis_label
                g.vary_label = "/".join(x.title() for x in vary) if isinstance(vary, tuple) else vary.title()
                g.vary_prefix = vary_units
                g.key_position = key_position

                for (attr_name, attr_value) in kwargs.items():
                    if hasattr(g, attr_name):
                        setattr(g, attr_name, attr_value)
                    else:
                        print(f"WARNING: The grapher does not have an attribute of name {attr_name}, not setting it.")

                if custom_yaxis_range_max is not None and yaxis in custom_yaxis_range_max:
                    g.yaxis_range_max = custom_yaxis_range_max[yaxis]

                if custom_yaxis_range_min is not None and yaxis in custom_yaxis_range_min:
                    g.yaxis_range_min = custom_yaxis_range_min[yaxis]

                if g.create(algo_results):
                    summary.GraphSummary(
                        os.path.join(self.algorithm_module.graphs_path(sim_name), name),
                        os.path.join(algorithm.results_directory_name, 'v-{}-{}'.format(self.algorithm_module.name, name))
                    ).run()

    def _create_baseline_versus_graph(self, sim_name, baseline_module, graph_parameters, varying, *,
                                      custom_yaxis_range_max=None, custom_yaxis_range_min=None,
                                      source_period_normalisation=None, network_size_normalisation=None, results_filter=None,
                                      yextractor=scalar_extractor, xextractor=None, testbed=None, #vary_label=None,
                                      **kwargs):
        from data.graph import baseline_versus

        algo_results = results.Results(
            sim_name, self.get_results_file_path(sim_name, testbed=testbed),
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation=source_period_normalisation,
            network_size_normalisation=network_size_normalisation,
            results_filter=results_filter)

        baseline_result_file_path = self.get_results_file_path(sim_name, testbed=testbed, module=baseline_module)
        baseline_analysis = baseline_module.Analysis.Analyzer(sim_name, baseline_result_file_path, testbed=testbed)

        graph_parameters_set = set(graph_parameters.keys())
        baseline_parameters_set = set(baseline_analysis.values.keys())

        if len(graph_parameters_set - baseline_parameters_set) != 0:
            print(f"Warning graph_parameters_set != baseline_parameters_set, extra = {graph_parameters_set - baseline_parameters_set}")

        baseline_parameters_to_load = tuple(graph_parameters_set & baseline_parameters_set)


        baseline_results = results.Results(
            sim_name, baseline_result_file_path,
            parameters=baseline_module.local_parameter_names,
            results=baseline_parameters_to_load,
            source_period_normalisation=source_period_normalisation,
            network_size_normalisation=network_size_normalisation,
            results_filter=results_filter)

        for ((xaxis, xaxis_units), (vary, vary_units)) in varying:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = f'{self._shorter_name(xaxis)}-bv-{self._shorter_name(yaxis)}-w-{self._shorter_name(vary)}'

                if isinstance(yextractor, dict):
                    try:
                        yextractor_single = yextractor[yaxis]
                    except KeyError:
                        yextractor_single = scalar_extractor
                else:
                    yextractor_single = scalar_extractor

                g = baseline_versus.Grapher(
                    sim_name, self.algorithm_module.graphs_path(sim_name), name,
                    xaxis=xaxis, yaxis=yaxis, vary=vary,
                    yextractor=yextractor_single, xextractor=xextractor)

                g.xaxis_label = xaxis.title()
                g.yaxis_label = yaxis_label
                g.vary_label = "/".join(x.title() for x in vary) if isinstance(vary, tuple) else vary.title()
                g.vary_prefix = vary_units
                g.key_position = key_position

                for (attr_name, attr_value) in kwargs.items():
                    if hasattr(g, attr_name):
                        setattr(g, attr_name, attr_value)
                    else:
                        print("WARNING: The grapher does not have an attribute of name {}, not setting it.".format(attr_name))

                if custom_yaxis_range_max is not None and yaxis in custom_yaxis_range_max:
                    g.yaxis_range_max = custom_yaxis_range_max[yaxis]

                if custom_yaxis_range_min is not None and yaxis in custom_yaxis_range_min:
                    g.yaxis_range_min = custom_yaxis_range_min[yaxis]                

                if g.create(algo_results, baseline_results):
                    summary.GraphSummary(
                        os.path.join(self.algorithm_module.graphs_path(sim_name), name),
                        os.path.join(algorithm.results_directory_name, 'bv-{}_{}-{}'.format(self.algorithm_module.name, baseline_module.name, name))
                    ).run()

    def _create_min_max_versus_graph(self, sim_name, comparison_modules, baseline_module, graph_parameters, varying, *,
                                     algo_results=None, custom_yaxis_range_max=None,
                                     source_period_normalisation=None, network_size_normalisation=None, results_filter=None,
                                     yextractor=None,
                                     **kwargs):
        from data.graph import min_max_versus

        if algo_results is None:
            algo_results = results.Results(
                sim_name, self.algorithm_module.result_file_path(sim_name),
                parameters=self.algorithm_module.local_parameter_names,
                results=tuple(graph_parameters.keys()),
                source_period_normalisation=source_period_normalisation,
                network_size_normalisation=network_size_normalisation,
                results_filter=results_filter)

        all_comparion_results = [
            results.Results(
                sim_name, comparion_module.result_file_path(sim_name),
                parameters=comparion_module.local_parameter_names,
                results=tuple(graph_parameters.keys()),
                source_period_normalisation=source_period_normalisation,
                network_size_normalisation=network_size_normalisation,
                results_filter=results_filter)
            if not hasattr(comparion_module, "data") else comparion_module

            for comparion_module in comparison_modules
        ]

        if baseline_module is not None:
            if hasattr(baseline_module, "data"):
                baseline_results = baseline_module
            else:
                baseline_results = results.Results(
                    sim_name, baseline_module.result_file_path(sim_name),
                    parameters=baseline_module.local_parameter_names,
                    results=tuple(graph_parameters.keys()))
        else:
            baseline_results = None

        for ((xaxis, xaxis_units), (vary, vary_units)) in varying:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = f'{self._shorter_name(xaxis)}-v-{self._shorter_name(yaxis)}-w-{self._shorter_name(vary)}'

                if isinstance(yextractor, dict):
                    try:
                        yextractor_single = yextractor[yaxis]
                    except KeyError:
                        yextractor_single = scalar_extractor
                else:
                    yextractor_single = scalar_extractor

                g = min_max_versus.Grapher(
                    sim_name, self.algorithm_module.graphs_path(sim_name), name,
                    xaxis=xaxis, yaxis=yaxis, vary=vary,
                    yextractor=yextractor_single)

                g.xaxis_label = xaxis.title()
                g.yaxis_label = yaxis_label
                g.vary_label = "/".join(x.title() for x in vary) if isinstance(vary, tuple) else vary.title()
                g.vary_prefix = vary_units
                g.key_position = key_position

                for (attr_name, attr_value) in kwargs.items():
                    if hasattr(g, attr_name):
                        setattr(g, attr_name, attr_value)
                    else:
                        print("WARNING: The grapher does not have an attribute of name {}, not setting it.".format(attr_name))

                if custom_yaxis_range_max is not None and yaxis in custom_yaxis_range_max:
                    g.yaxis_range_max = custom_yaxis_range_max[yaxis]

                if g.create(all_comparion_results, algo_results, baseline_results=baseline_results):
                    summary.GraphSummary(
                        os.path.join(self.algorithm_module.graphs_path(sim_name), name),
                        os.path.join(algorithm.results_directory_name,
                                     'mmv-{}_{}-{}'.format(self.algorithm_module.name,
                                     "_".join(mod.name for mod in comparison_modules), name))
                    ).run()

    def _create_multi_versus_graph(self, sim_name, graph_parameters, xaxes, yaxis_label, *,
                                   custom_yaxis_range_max=None,
                                   source_period_normalisation=None, network_size_normalisation=None, results_filter=None,
                                   yextractor=scalar_extractor, xextractor=None,
                                   **kwargs):
        from data.graph import multi_versus

        vary = tuple(x[0] for x in graph_parameters)

        algo_results = results.Results(
            sim_name, self.algorithm_module.result_file_path(sim_name),
            parameters=self.algorithm_module.local_parameter_names,
            results=vary,
            source_period_normalisation=source_period_normalisation,
            network_size_normalisation=network_size_normalisation,
            results_filter=results_filter)

        for (xaxis, xaxis_units) in xaxes:

            name = '{}-mv-{}'.format(xaxis, "-".join(vary)).replace(" ", "_")

            g = multi_versus.Grapher(
                sim_name, self.algorithm_module.graphs_path(sim_name), name,
                xaxis=xaxis, varying=graph_parameters,
                yaxis_label=yaxis_label,
                yextractor=yextractor, xextractor=xextractor)

            g.xaxis_label = xaxis.title()
            g.yaxis_label = yaxis_label
            g.vary_label = ""

            for (attr_name, attr_value) in kwargs.items():
                if hasattr(g, attr_name):
                    setattr(g, attr_name, attr_value)
                else:
                    print(f"WARNING: The grapher does not have an attribute of name {attr_name}, not setting it.")

            if custom_yaxis_range_max is not None:
                g.yaxis_range_max = custom_yaxis_range_max

            if g.create(algo_results):
                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path(sim_name), name),
                    os.path.join(algorithm.results_directory_name, 'mv-{}-{}'.format(self.algorithm_module.name, name))
                ).run()

    def _get_extra_plural_name(self, name):
        parameters = self.algorithm_module.Parameters

        non_plural_names = ["low power listening"]

        if name in non_plural_names:
            return getattr(parameters, name.replace(" ", "_"))

        for appendix in ("s", "es", ""):
            try:
                return getattr(parameters, name.replace(" ", "_") + appendix)
            except AttributeError:
                continue

        raise RuntimeError(f"Unable to find plural of {name}")

    def _get_global_parameter_values(self, sim, parameters):
        product_argument = []

        # Some arguments are non-plural
        non_plural_global_parameters = ("distance", "latest node start time")

        # Some arguments are not properly named
        synonyms = {
            "network size": "sizes",
        }

        def _get_global_plural_name(global_name):
            plural_name = synonyms.get(global_name, None)
            if plural_name is not None:
                return plural_name
            return global_name.replace(" ", "_") + "s"

        # First lets sort out the global parameters
        for global_name in sim.global_parameter_names:
            if global_name in non_plural_global_parameters:
                product_argument.append([getattr(parameters, global_name.replace(" ", "_"))])
            else:
                product_argument.append(getattr(parameters, _get_global_plural_name(global_name)))

        return product_argument

    def _get_local_parameter_values(self, parameters, local_name, custom_mapping=None):

        if custom_mapping is not None:
            value = custom_mapping.get(local_name, None)
            if value is not None:
                try:
                    return getattr(parameters, value)
                except AttributeError:
                    pass

        for appendix in ["s", "es", ""]:
            try:
                return getattr(parameters, local_name.replace(" ", "_") + appendix)
            except AttributeError:
                continue

        raise RuntimeError(f"Unable to find plural of {local_name}")

    def _argument_product(self, sim, extras=None):
        """Produces the product of the arguments specified in a Parameters.py file of the self.algorithm_module.

        Algorithms that do anything special will need to implement this themselves.
        """
        # Lets do our best to implement an argument product that we can expect an algorithm to need.
        parameters = self.algorithm_module.Parameters

        product_argument = []

        product_argument.extend(self._get_global_parameter_values(sim, parameters))

        # Now lets process the algorithm specific parameters
        for local_name in self.algorithm_module.local_parameter_names:
            product_argument.append(self._get_local_parameter_values(parameters, local_name))

        if extras:
            for extra_name in extras:
                product_argument.append(self._get_extra_plural_name(extra_name))

        argument_product = itertools.product(*product_argument)

        # Factor in the number of sources when selecting the source period.
        # This is done so that regardless of the number of sources the overall
        # network's normal message generation rate is the same.
        argument_product = self.adjust_source_period_for_multi_source(sim, argument_product)

        return argument_product

    def add_extra_arguments(self, argument_product, extras):
        if extras is None or len(extras) == 0:
            return argument_product

        extras = [self._get_extra_plural_name(extra) for extra in extras]

        extras_product = itertools.product(*extras)

        return [x + y for (x, y) in itertools.product(argument_product, extras_product)]

    def time_after_first_normal_to_safety_period(self, time_after_first_normal):
        return time_after_first_normal

    def _execute_runner(self, sim_name, driver, result_path, time_estimator=None,
                        skip_completed_simulations=True, verbose=False, debug=False, min_repeats=1):
        testbed_name = None

        if driver.mode() in {"TESTBED", "PLATFORM"}:
            from data.run.common import RunTestbedCommon as RunSimulations
            if driver.mode() == "TESTBED":
                testbed_name = driver.testbed_name()
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

        sim = submodule_loader.load(simulator.sim, sim_name)

        if not driver.required_safety_periods:
            safety_periods = False
        elif self.safety_period_module_name is True:
            safety_periods = True
        elif self.safety_period_module_name is None:
            safety_periods = None
        else:
            safety_period_table_generator = safety_period.TableGenerator(
                sim_name,
                self.get_safety_period_result_path(sim_name, testbed=testbed_name),
                self.time_after_first_normal_to_safety_period)
            
            safety_periods = safety_period_table_generator.safety_periods()

        runner = RunSimulations(
            sim_name, driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations,
            safety_periods=safety_periods,
            safety_period_equivalence=self.safety_period_equivalence,
        )

        extra_argument_names = getattr(runner, "extra_arguments", tuple())

        argument_product = self._argument_product(sim, extras=extra_argument_names)

        argument_product_duplicates = _duplicates_in_iterable(argument_product)

        if len(argument_product_duplicates) > 0:
            from pprint import pprint
            print("There are duplicates in your argument product, check your Parameters.py file.")
            print("The following parameters have duplicates of them:")
            pprint(argument_product_duplicates)
            raise RuntimeError("There are duplicates in your argument product, check your Parameters.py file.")

        if time_estimator is not None:
            time_estimator = functools.partial(time_estimator, sim_name)

        try:
            runner.run(self.algorithm_module.Parameters.repeats,
                       self.parameter_names(sim) + extra_argument_names,
                       argument_product,
                       time_estimator,
                       verbose=verbose,
                       debug=debug,
                       min_repeats=min_repeats)
        except MissingSafetyPeriodError as ex:
            from pprint import pprint
            import traceback
            print(traceback.format_exc())
            print("Available safety periods:")
            pprint(ex.safety_periods)

    def adjust_source_period_for_multi_source(self, sim, argument_product):
        """For configurations with multiple sources, so that the network has the
        overall same message generation rate, the source period needs to be adjusted
        relative to the number of sources."""
        names = self.parameter_names(sim)
        source_period_index = names.index('source period')

        def process(args):
            dargs = {**dict(zip(names, args)), "seed": None, "node id order": "topology"}
            configuration = Configuration.create(dargs["configuration"], dargs)
            num_sources = len(configuration.source_ids)

            source_period = args[source_period_index] * num_sources
            return args[:source_period_index] + (source_period,) + args[source_period_index+1:]

        return [process(args) for args in argument_product]

    def _default_cluster_time_estimator(self, sim_name, args, **kwargs):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        size = args['network size']

        if sim_name == "cooja":
            if size == 5:
                return timedelta(hours=12)
            elif size == 7:
                return timedelta(hours=24)
            elif size == 9:
                return timedelta(hours=48)
            elif size == 11:
                return timedelta(hours=71)
            elif size == 13:
                return timedelta(hours=71)
            elif size == 15:
                return timedelta(hours=71)
            else:
                raise RuntimeError("No time estimate for network sizes other than 5, 7, 9, 11, 13 or 15")
        else:
            if size == 7:
                return timedelta(hours=7)
            elif size == 11:
                return timedelta(hours=9)
            elif size == 15:
                return timedelta(hours=21)
            elif size == 21:
                return timedelta(hours=42)
            elif size == 25:
                return timedelta(hours=71)
            else:
                raise RuntimeError("No time estimate for network sizes other than 7, 11, 15, 21 or 25")

    def _cluster_time_estimator(self, sim_name, args, **kwargs):
        return self._default_cluster_time_estimator(sim_name, args, **kwargs)

    def _cluster_time_estimator_from_historical(self, sim, args, kwargs, historical_key_names, historical, allowance=0.2, max_time=None):
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

            # Always ask for at least 2 minutes
            calculated_time = timedelta(minutes=2) + time_per_proc_with_allowance + extra_time

            if max_time is not None:
                if calculated_time > max_time:
                    print(f"Warning: The estimated cluster time is {calculated_time}, overriding this with the maximum set time of {max_time}")
                    calculated_time = max_time

            return calculated_time

        except KeyError:
            print(f"Unable to find historical time for {key} on {sim}, so using default time estimator.")
            return self._default_cluster_time_estimator(sim, args, **kwargs)

    def _run_run(self, args):
        from data.run.driver import local as LocalDriver
        driver = LocalDriver.Runner()

        try:
            driver.job_thread_count = int(args.thread_count)
        except TypeError:
            # None tells the runner to use the default
            driver.job_thread_count = None

        skip_complete = not args.no_skip_complete

        self._execute_runner(args.sim, driver, self.algorithm_module.results_path(args.sim),
                             time_estimator=None,
                             skip_completed_simulations=skip_complete)

    def _run_analyse(self, args):
        def results_finder(results_directory):
            return fnmatch.filter(os.listdir(results_directory), '*.txt')

        analyzer = self.algorithm_module.Analysis.Analyzer(args.sim, self.algorithm_module.results_path(args.sim))
        analyzer.run(self.algorithm_module.result_file,
                     results_finder,
                     nprocs=args.thread_count,
                     flush=args.flush,
                     headers_to_skip=args.headers_to_skip,
                     keep_if_hit_upper_time_bound=args.keep_if_hit_upper_time_bound)

    def _run_testbed_analyse(self, testbed, args):
        def results_finder(results_directory):
            return fnmatch.filter(os.listdir(results_directory), '*.txt')

        results_path = self._testbed_results_path(testbed)
        result_file = os.path.basename(self.algorithm_module.result_file)

        analyzer = self.algorithm_module.Analysis.Analyzer("real", results_path, testbed=testbed)
        analyzer.run(result_file,
                     results_finder,
                     nprocs=args.thread_count,
                     flush=args.flush,
                     headers_to_skip=args.headers_to_skip,
                     keep_if_hit_upper_time_bound=args.keep_if_hit_upper_time_bound,
                     testbed=True)

    def _run_testbed_run(self, testbed, args):
        import multiprocessing.pool

        output_results_path = self._testbed_results_path(testbed)
        input_results_path = os.path.join("testbed_results", testbed.name(), self.algorithm_module.name)

        create_dirtree(output_results_path)

        excluded_dirs = {"bad"}

        results_dirs = [
            d
            for d in os.listdir(input_results_path)
            if os.path.isdir(os.path.join(input_results_path, d)) and d not in excluded_dirs
        ]

        if not results_dirs:
            raise RuntimeError(f"No directories to analyse in {input_results_path}")

        # All directories that have results for the same parameters
        common_results_dirs = {result_dirs.rsplit("_", 1)[0] for result_dirs in results_dirs}

        if self.safety_period_module_name is True:
            if self.custom_run_simulation_class is None:
                raise RuntimeError("NEED TO HAVE CUSTOM SIMULATOR CLASS")

            def safety_periods(safety_key, local_params_values, source_period):
                safety_key_names = ("configuration", "attacker model", "fault model", "node id order", "tx power", "channel", "lpl")
                
                dargs = dict(zip(safety_key_names, safety_key))
                dargs["source period"] = source_period
                dargs.update(local_params_values)

                # Hopefully they don't use the self variable
                return str(self.custom_run_simulation_class._get_safety_period(None, dargs))

        elif self.safety_period_module_name is None:
            safety_periods = None
        else:
            safety_period_result_path = self.get_safety_period_result_path("real", testbed=testbed)
            safety_period_table = safety_period.TableGenerator("real",
                                                               safety_period_result_path,
                                                               self.time_after_first_normal_to_safety_period)
            safety_periods_table = safety_period_table.safety_periods()

            def safety_periods(safety_key, local_params_values, source_period):
                return str(safety_periods_table[safety_key][source_period])

        commands = []


        # Some results have had lpl parameters renamed to save space
        # "disabled" => "0", "enabled" => "1"
        # We want these results to go into the same output file

        to_process = defaultdict(list)

        for common_result_dir in common_results_dirs:

            params = list(common_result_dir.split("-"))
            if params[3] == "0":
                params[3] = "disabled"
            if params[3] == "1":
                params[3] = "enabled"

            to_process["-".join(params)].append(common_result_dir)

        for (out_param, in_params) in to_process.items():

            log_files = " ".join(os.path.join(input_results_path, x + "_*", testbed.result_file_name) for x in in_params)

            command = "python3 -OO -X faulthandler run.py algorithm.{} offline SINGLE --log-converter {} --log-file {} --non-strict ".format(
                self.algorithm_module.name,
                testbed.name(),
                log_files)

            settings = {
                "--attacker-model": args.attacker_model,
            }

            testbed_extra_metrics = getattr(testbed, "extra_metrics", [])
            if testbed_extra_metrics:
                settings["--extra-metrics"] = " ".join(testbed_extra_metrics)

            # The source period will either be the second or third entry in out_param
            # Depending on if the fault model has been left out
            params = out_param.split("-")

            if len(params) == 5 + len(self.algorithm_module.local_parameter_names):
                (configuration, tx_power, channel, lpl, source_period), local_params = params[:5], params[5:]
                fault_model = "ReliableFaultModel()"
            #elif len(params) == 3 + len(self.algorithm_module.local_parameter_names):
            #    (configuration, source_period) = params[:2]
            #    fault_model = "ReliableFaultModel()"
            else:
                raise RuntimeError("Unsure of arguments that the testbed job was run with")

            settings["--configuration"] = configuration
            settings["--fault-model"] = fault_model

            if safety_periods:
                source_period = source_period.replace("_", ".")

                safety_key = (configuration, str(args.attacker_model), fault_model, 'topology', tx_power, channel, 'disabled')
                local_params_values = dict(zip(self.algorithm_module.local_parameter_names, local_params))
                settings["--safety-period"] = safety_periods(safety_key, local_params_values, source_period)
            
            command += " ".join(f"{k} \"{v}\"" for (k, v) in settings.items())

            if args.verbose:
                command += " --verbose"

            out_path = os.path.join(output_results_path, out_param + ".txt")

            commands.append((command, out_path))

        def runner(arguments):
            (command, out_path) = arguments
            print("Executing:", command, ">", out_path)
            with open(out_path, "w") as stdout_file:
                subprocess.check_call(command, stdout=stdout_file, shell=True)

        job_pool = multiprocessing.pool.ThreadPool(processes=args.thread_count)

        try:
            job_pool.map(runner, commands)
        finally:
            job_pool.terminate()


    def _run_safety_table(self, args):
        safety_period_result_path = self.get_safety_period_result_path(args.sim, testbed=args.testbed)

        safety_period_table = safety_period.TableGenerator(args.sim,
                                                           safety_period_result_path,
                                                           self.time_after_first_normal_to_safety_period)

        if args.testbed:
            print("Writing testbed safety period table...")

            filename = f'{self.algorithm_module.name}-safety'

            self._create_table(filename, safety_period_table, directory="testbed_results", show=args.show)

        else:

            if args.sim == "tossim":
                names = ("noise model", "communication model")
                prod = list(itertools.product(NoiseModel.available_models(),
                                              CommunicationModel.available_models()))
            else:
                names = tuple()
                prod = []

            if len(prod) > 0:
                for p in prod:
                    print(f"Writing results table for {' and '.join(str(x) for x in p)}")

                    filename = f'{self.algorithm_module.name}-{args.sim}-{"-".join(str(x) for x in p)}-safety'

                    self._create_table(filename, safety_period_table,
                                       param_filter=lambda x: all(x[name] == value for (name, value) in zip(names, p)))
            else:
                filename = f'{self.algorithm_module.name}-{args.sim}-safety'

                self._create_table(filename, safety_period_table, show=args.show)


    def _run_error_table(self, args):
        res = results.Results(
            args.sim, self.algorithm_module.result_file_path(args.sim),
            parameters=self.algorithm_module.local_parameter_names,
            results=('dropped no sink delivery', 'dropped hit upper bound', 'dropped duplicates'))

        result_table = fake_result.ResultTable(res)

        self._create_table(self.algorithm_module.name + "-error-results", result_table, show=args.show)

    def _run_convergence_table(self, args):
        from data.table.summary_formatter import TableDataFormatter
        fmt = TableDataFormatter()

        parameters = [
            'repeats',
            'time taken',
            'received ratio',
            'captured',
            'normal latency',
            'norm(sent,time taken)',
            'attacker distance',
        ]

        def results_filter(params):
            return (
                params.get("noise model", "casino-lab") != "casino-lab" or
                params["configuration"] != "SourceCorner" or
                params["source period"] == "0.125" or
                params["network size"] == "5"
            )

        hide_parameters = [
            'buffer size', 'max walk length', 'pr direct to sink', # ILPRouting
            'pr pfs', # Template
        ]
        caption_values = ["network size"]

        extractors = {
            # Just get the distance of attacker 0 from node 0 (the source in SourceCorner)
            "attacker distance": lambda yvalue: yvalue[(0, 0)]
        }

        self._create_results_table(args.sim, parameters,
            fmt=fmt, results_filter=results_filter, hide_parameters=hide_parameters, extractors=extractors, resize_to_width=True,
            caption_values=caption_values, show=args.show)

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

        # Only provide unique emails
        return list(unique_everseen(emails_to_notify))

    def _run_cluster(self, args):
        cluster_directory = os.path.join("cluster", self.algorithm_module.name)

        cluster = clusters.create(args.name)

        if 'build' == args.cluster_mode:
            print("Removing existing cluster directory and creating a new one")
            recreate_dirtree(cluster_directory)
            touch(os.path.join(os.path.dirname(cluster_directory), "__init__.py"))
            touch(os.path.join(cluster_directory, "__init__.py"))

            skip_complete = not args.no_skip_complete

            self._execute_runner(args.sim, cluster.builder(args.sim), cluster_directory,
                                 time_estimator=None,
                                 skip_completed_simulations=skip_complete)

        elif 'copy' == args.cluster_mode:
            cluster.copy_to(self.algorithm_module.name, user=args.user)

        elif 'copy-result-summary' == args.cluster_mode:
            cluster.copy_file(self.algorithm_module.results_path(args.sim), self.algorithm_module.result_file, user=args.user)

        elif 'copy-parameters' == args.cluster_mode:
            cluster.copy_file(os.path.join('algorithm', self.algorithm_module.name), 'Parameters.py', user=args.user)

        elif 'submit' == args.cluster_mode:
            emails_to_notify = self._get_emails_to_notify(args)

            submitter_fn = cluster.array_submitter if args.array else cluster.submitter

            submitter = submitter_fn(args.sim, notify_emails=emails_to_notify, dry_run=args.dry_run, unhold=args.unhold)

            skip_complete = not args.no_skip_complete

            self._execute_runner(args.sim, submitter, cluster_directory,
                                 time_estimator=self._cluster_time_estimator,
                                 skip_completed_simulations=skip_complete,
                                 min_repeats=args.min_repeats)

        elif 'copy-back' == args.cluster_mode:
            cluster.copy_back(self.algorithm_module.name, args.sim, user=args.user)

        else:
            raise RuntimeError(f"Unknown cluster mode {args.cluster_mode}")

        sys.exit(0)

    def _run_testbed(self, args):
        testbed_directory = os.path.join("testbed", self.algorithm_module.name)

        testbed = submodule_loader.load(data.testbed, args.name)

        if 'build' == args.testbed_mode:
            from data.run.driver.testbed_builder import Runner as Builder

            print(f"Removing existing testbed directory {testbed_directory} and creating a new one")
            recreate_dirtree(testbed_directory)

            builder = Builder(testbed, platform=args.platform)

            self._execute_runner("real", builder, testbed_directory,
                                 time_estimator=None,
                                 skip_completed_simulations=False,
                                 verbose=args.verbose,
                                 debug=args.debug)

        elif 'submit' == args.testbed_mode:

            duration = time.strptime(args.duration, "%H:%M:%S")
            duration = timedelta(hours=duration.tm_hour, minutes=duration.tm_min, seconds=duration.tm_sec)

            # Add some extra time to account for the period spent waiting for serial to be ready
            extra_minutes = timedelta(minutes=testbed.build_arguments().get("DELAYED_BOOT_TIME_MINUTES", 0))

            duration += extra_minutes
            

            submitter = testbed.submitter(duration=duration, dry_run=args.dry_run)

            skip_complete = not args.no_skip_complete

            self._execute_runner("real", submitter, testbed_directory,
                                 time_estimator=None,
                                 skip_completed_simulations=skip_complete)

        elif 'run' == args.testbed_mode:
            self._run_testbed_run(testbed, args)

        elif 'analyse' == args.testbed_mode:
            self._run_testbed_analyse(testbed, args)

        sys.exit(0)

    def _run_platform(self, args):
        platform = args.name

        platform_directory = os.path.join("platform", platform, self.algorithm_module.name)

        if 'build' == args.platform_mode:
            from data.run.driver.platform_builder import Runner as Builder

            print(f"Removing existing platform directory {platform_directory} and creating a new one")
            recreate_dirtree(platform_directory)

            builder = Builder(platform, args.log_mode,
                              generate_per_node_id_binary=args.generate_per_node_id_binary)

            self._execute_runner("real", builder, platform_directory,
                                 time_estimator=None,
                                 skip_completed_simulations=False,
                                 verbose=args.verbose,
                                 debug=args.debug)

        sys.exit(0)

    def _run_time_taken_table(self, args):
        result_file_path = self.get_results_file_path(args.sim, testbed=args.testbed)

        result = results.Results(args.sim,
                                 result_file_path,
                                 parameters=self.algorithm_module.local_parameter_names,
                                 results=('time taken', 'first normal sent time',
                                          'total wall time', 'wall time', 'event count',
                                          'repeats', 'captured', 'reached upper bound',
                                          #'memory rss',
                                          'memory vms'),
        )

        result_table = fake_result.ResultTable(result)

        self._create_table(self.algorithm_module.name + "-time-taken", result_table, orientation="landscape", show=args.show)

    def _run_detect_missing(self, args):
        import difflib

        sim = submodule_loader.load(simulator.sim, args.sim)
        result_file_path = self.algorithm_module.result_file_path(args.sim)

        def _format_item(name, item):
            if name == "radio model":
                return str(CoojaRadioModel.eval_input(item))
            else:
                return str(item)

        names = sim.global_parameter_names + self.algorithm_module.local_parameter_names

        argument_product = {
            tuple(_format_item(name, item) for (name, item) in zip_equal(names, row))
            for row
            in self._argument_product(sim)
        }

        result = results.Results(args.sim, result_file_path,
                                 parameters=self.algorithm_module.local_parameter_names,
                                 results=('repeats',))

        repeats = {tuple(map(str, k)): v for (k, v) in result.parameter_set().items()}
        repeats_diff_strings = ["|".join(k) for k in repeats.keys()]

        parameter_names = sim.global_parameter_names + result.parameter_names

        if args.show_all:
            from pprint import pprint
            print("All results:")
            pprint(repeats)

            print("User parameters:")
            pprint(argument_product)

        print("Checking runs that were asked for, but not included...")

        for arguments in sorted(argument_product):
            if arguments not in repeats:
                print(f"Missing {arguments}")
                print(", ".join([f"{n}={str(v)}" for (n,v) in zip(parameter_names, arguments)]))

                close_matches = difflib.get_close_matches("|".join(arguments), repeats_diff_strings, n=3)

                if len(close_matches) > 0:
                    print("Close:")
                    for close in close_matches:
                        print(f"\t{close.split('|')}")
                else:
                    print("No close matches to existing results")
                
                print()

        print(f"Loading {result_file_path} to check for missing runs...")

        for (parameter_values, repeats_performed) in repeats.items():

            if parameter_values not in argument_product:
                continue

            repeats_missing = max(self.algorithm_module.Parameters.repeats - repeats_performed, 0)

            # Number of repeats is below the target
            if repeats_missing > 0:
                print(f"performed={repeats_performed} missing={repeats_missing} ", end="")
                print(", ".join([f"{n}={str(v)}" for (n,v) in zip(parameter_names, parameter_values)]))
                print()

    def _run_graph_heatmap(self, args):
        analyser = self.algorithm_module.Analysis.Analyzer(args.sim, self.algorithm_module.results_path(args.sim))

        heatmap_results = [
            header
            for header
            in analyser.results_header().keys()
            if header.endswith('heatmap')
        ]

        results_summary = results.Results(
            args.sim, self.algorithm_module.result_file_path(args.sim),
            parameters=self.algorithm_module.local_parameter_names,
            results=heatmap_results)

        for name in heatmap_results:
            heatmap.Grapher(args.sim, self.algorithm_module.graphs_path(args.sim), results_summary, name).create()
            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path(args.sim), name),
                os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name.replace(" ", "_")))
            ).run()

    def _run_per_parameter_grapher(self, args):
        import data.graph as data_graph

        graph_type = submodule_loader.load(data_graph, args.grapher)

        analyzer = self.algorithm_module.Analysis.Analyzer(self.algorithm_module.results_path)

        grapher = graph_type.Grapher(
            args.sim, os.path.join(self.algorithm_module.graphs_path(args.sim), args.grapher),
            args.metric_name,
            self.parameter_names(args.sim)
        )

        grapher.xaxis_label = args.metric_name

        grapher.create(analyzer,
                       with_converters=not args.without_converters,
                       with_normalised=not args.without_normalised
        )

        summary.GraphSummary(
            os.path.join(self.algorithm_module.graphs_path(args.sim), args.grapher),
            os.path.join(algorithm.results_directory_name, f"{self.algorithm_module.name}-{args.grapher}")
        ).run(show=args.show)

    def _run_graph_convergence(self, args):
        import matplotlib.pyplot as plt
        import numpy as np
        from scipy import stats

        def results_finder(results_directory):
            return fnmatch.filter(os.listdir(results_directory), '*.txt')

        results_directory = self.algorithm_module.results_path(args.sim)

        print(results_directory)

        analyzer = self.algorithm_module.Analysis.Analyzer(args.sim, results_directory)

        #def dennis_convergence(window, alpha=0.01):
        #    return abs(window[1] - window[0]) <= alpha * window[0]
            

        # Possible alternatives
        # https://stats.stackexchange.com/questions/195020/how-to-test-whether-a-time-series-of-measurements-have-converged-to-an-equilibri
        # https://en.wikipedia.org/wiki/Convergence_tests

        def ci(values):
            sample_mean = values.mean()

            confidence_interval_95 = stats.t.interval(
                alpha=0.95,             # Confidence level
                df=values.count()-1,
                loc=sample_mean,
                scale=values.sem())

            return confidence_interval_95[1] - sample_mean

        result_basedir = f"results/conv/{args.sim}/{self.algorithm_module.name}"
        create_dirtree(result_basedir)

        files = sorted(results_finder(results_directory))
        for num, infile in enumerate(files):
            path = os.path.join(results_directory, infile)

            print(f'Analysing {path}')

            res = analyzer.analyse_path(path)

            factor = 2.5
            f, axes = plt.subplots(len(args.headers), 3, figsize=(5*factor,4*factor))

            axes[0][0].set_title("Values")
            axes[0][1].set_title("Histogram")
            axes[0][2].set_title("Expanding Mean")
            #axes[0][3].set_title("Denis Convergence $\\alpha=0.01$")

            for (i, header) in enumerate(args.headers):
                col = res.find_column(header).astype(float)

                expcol = col.expanding()

                expcol_mean = expcol.mean()
                expcol_cis = expcol.apply(ci, raw=False)
                expcol_ciu = expcol_mean + expcol_cis
                expcol_cil = expcol_mean - expcol_cis

                axes[i, 0].plot(col)
                axes[i, 0].set_ylabel(header)

                axes[i, 1].hist(col, bins=50)
                axes[i, 1].axvline(col.mean(), color='k', linestyle='dashed', linewidth=1)

                axes[i, 2].plot(expcol_mean)
                axes[i, 2].plot(expcol_ciu)
                axes[i, 2].plot(expcol_cil)
                axes[i, 2].set_ylim(bottom=expcol_cil.tail(expcol_cil.count()-50).min(),
                                    top=expcol_ciu.tail(expcol_ciu.count()-50).max())
                #axes[i, 2].legend(['Mean', 'Upper 95% CI', 'Lower 95% CI'], loc='lower right')

                #dccol = expcol.rolling(2).apply(dennis_convergence, kwargs={"alpha": 0.01}, raw=True)

                #j = None
                #g = None
                #for j, g in dccol.groupby([(dccol != dccol.shift()).cumsum()]):
                #    pass
                #print("j", j, "g", g.size /  dccol.size, g.iloc[0])

                #axes[i, 3].plot(dccol)

            if args.show:
                plt.show()
            else:
                plt.savefig(f"{result_basedir}/{infile}.pdf", aspect='auto', bbox_inches='tight', dpi=300)


    def _run_historical_time_estimator(self, args):
        sim = submodule_loader.load(simulator.sim, args.sim)

        result = results.Results(args.sim, self.algorithm_module.result_file_path(args.sim),
                                 parameters=self.algorithm_module.local_parameter_names,
                                 results=('total wall time',))

        max_wall_times = defaultdict(float)

        # For each network size and source period find the maximum total wall time

        for (global_params, values1) in result.data.items():

            global_params = dict(zip(sim.global_parameter_names, global_params))

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

        if hasattr(args, "sim"):
            create_dirtree(self.algorithm_module.results_path(args.sim))
            create_dirtree(self.algorithm_module.graphs_path(args.sim))

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
