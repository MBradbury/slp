from __future__ import print_function, division

import itertools
import os
import datetime

from simulator import CommandLineCommon

import algorithm

algorithm_module = __import__(__package__, globals(), locals(), ['object'], -1)

protectionless_tdma_das = algorithm.import_algorithm("protectionless_tdma_das")

from data import results
from data.run.common import RunSimulationsCommon
from data.graph import summary, versus, baseline_versus, bar
from data.table import safety_period
from data.util import scalar_extractor

class RunSimulations(RunSimulationsCommon):
    def _get_safety_period(self, darguments):
        # tafn = super(RunSimulations, self)._get_safety_period(darguments)

        header_params = algorithm_module.get_parameters_in_header(darguments["genetic header"])

        network_size = darguments["network size"]
        dissem_period = darguments["dissem period"]
        slot_period = darguments["slot period"]
        tdma_num_slots = header_params["GA_TOTAL_SLOTS"]
        tdma_period_length = dissem_period + (slot_period * tdma_num_slots)
        ssd = network_size - 1                                                  #XXX Cheap fix until I find the real solution

        return (1 + ssd)*tdma_period_length*2

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, True, RunSimulations)

        subparser = self._add_argument("graph", self._run_graph)
        subparser = self._add_argument("graph-versus-baseline", self._run_graph_versus_baseline)
        subparser = self._add_argument("graph-bar", self._run_graph_bar)

    def _cluster_time_estimator(self, args, **kwargs):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        size = args['network size']
        if size == 11:
            return datetime.timedelta(hours=4) #Assuming 100 slots and 5.5s period length
        elif size == 15:
            return datetime.timedelta(hours=12) #Assuming 100 slots and 5.5s period length
        elif size == 21:
            return datetime.timedelta(hours=1)
        elif size == 25:
            return datetime.timedelta(hours=1)
        else:
            raise RuntimeError("No time estimate for network sizes other than 11, 15, 21 or 25")

    # # Override default
    # def parameter_names(self):
        # # Remove source period from names
        # return self.global_parameter_names[:-1] + self.algorithm_module.local_parameter_names

    def _argument_product(self, extras=None):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models,
            parameters.communication_models, parameters.fault_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.slot_period, parameters.dissem_period,
            parameters.ga_headers, parameters.source_periods
        ))

        argument_product = self.add_extra_arguments(argument_product, extras)

        # Can't do this as source period is no longer a parameter
        #argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'attacker distance': ('Meters', 'left top'),
        }

        slp_tdma_das_ga_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()))

        for (vary, vary_prefix) in [("source period", " seconds")]:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-{}'.format(yaxis.replace(" ", "_"), vary.replace(" ", "-"))

                g = versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis='network size', yaxis=yaxis, vary=vary,
                    yextractor=scalar_extractor)

                g.xaxis_label = 'Network Size'
                g.yaxis_label = yaxis_label
                g.vary_label = vary.title()
                g.vary_prefix = vary_prefix
                g.key_position = key_position

                g.create(slp_tdma_das_ga_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name))
                ).run()

    def _run_graph_versus_baseline(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'attacker distance': ('Meters', 'left top'),
            'norm(sent,time taken)': ('Messages Sent per Second', 'left top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
        }

        protectionless_tdma_das_results = results.Results(
            protectionless_tdma_das.result_file_path,
            parameters=protectionless_tdma_das.local_parameter_names,
            results=list(set(graph_parameters.keys()) & set(protectionless_tdma_das.Analysis.Analyzer.results_header().keys())))

        slp_tdma_das_ga_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()))

        for (vary, vary_prefix) in [("source period", " seconds")]:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-baseline-{}'.format(yaxis.replace(" ", "_"), vary.replace(" ", "-"))

                g = baseline_versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis='network size', yaxis=yaxis, vary=vary,
                    yextractor=scalar_extractor)

                g.xaxis_label = 'Network Size'
                g.yaxis_label = yaxis_label
                g.vary_label = vary.title() + " -"
                #g.vary_prefix = vary_prefix
                g.key_position = key_position

                g.force_vvalue_label = True
                g.result_label = "SLP TDMA DAS GA"
                g.baseline_label = "Protectionless TDMA DAS"

                g.nokey = True
                g.generate_legend_graph = True
                g.legend_font_size = '8'

                g.create(slp_tdma_das_ga_results, baseline_results=protectionless_tdma_das_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name))
                ).run()

    def _run_graph_bar(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'right top'),
            'ssd': ('Sink-Source Distance (hops)', 'right top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'right top'),
            'received ratio': ('Receive Ratio (%)', 'right top'),
            'attacker distance': ('Meters', 'right top'),
            'norm(sent,time taken)': ('Messages Sent per Second', 'left top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per Node per Second', 'left top'),
        }

        vary = "genetic header"

        parameters = self.algorithm_module.local_parameter_names
        if vary not in parameters:
            parameters += (vary,)

        slp_tdma_das_ga_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=parameters + ('fitness function',),
            results=tuple(graph_parameters.keys()))

        def xextractor(xname):
            return "/".join(x.replace("slot-with-path-", "").replace("low-asymmetry", "low") for x in xname)

        def vextractor(vvalue):
            return int(vvalue.replace(".h", "").replace("dist", "").replace("slot", ""))

        for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
            name = '{}-v-{}'.format(yaxis.replace(" ", "_"), "gh")#vary.replace(" ", "-"))

            g = bar.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis=('communication model', 'fitness function'), yaxis=yaxis, vary=vary,
                yextractor=scalar_extractor)

            g.nokey = True
            g.yaxis_label = yaxis_label
            g.key_position = key_position
            g.xextractor = xextractor
            g.vextractor = vextractor
            g.xtics_around_cluster = True

            g.create(slp_tdma_das_ga_results)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name))
            ).run()
