from __future__ import print_function, division

import itertools
import os
import datetime

import simulator.sim
from simulator import CommandLineCommon
import simulator.Configuration

import algorithm

protectionless_tdma_das = algorithm.import_algorithm("protectionless_tdma_das", extras=["Analysis"])

from data import results, submodule_loader
from data.run.common import RunSimulationsCommon
from data.graph import summary, versus, baseline_versus
from data.table import safety_period
from data.util import scalar_extractor

class RunSimulations(RunSimulationsCommon):
    def _get_safety_period(self, darguments):
        # tafn = super(RunSimulations, self)._get_safety_period(darguments)

        #XXX Ugly hack using 0 as seed but we need the config only for SSD
        configuration = simulator.Configuration.create(darguments["configuration"], {"seed":0, **darguments})
        (source_id,) = configuration.source_ids
        (sink_id,) = configuration.sink_ids

        search_distance = int(darguments["search distance"])
        dissem_period = float(darguments["dissem period"])
        slot_period = float(darguments["slot period"])
        tdma_num_slots = int(darguments["tdma num slots"])
        tdma_period_length = dissem_period + (slot_period * tdma_num_slots)
        ssd = configuration.ssd(sink_id, source_id)
        change_distance = ssd // 3
        path_length = search_distance + change_distance

        # return path_length*tdma_period_length
        return (1 + ssd)*tdma_period_length*1.5

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        # super(CLI, self).__init__(protectionless_tdma_das.result_file_path, RunSimulations)
        super(CLI, self).__init__(True, RunSimulations)

        subparser = self._add_argument("graph", self._run_graph)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser = self._add_argument("graph-versus-baseline", self._run_graph_versus_baseline)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

    def _cluster_time_estimator(self, sim, args, **kwargs):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        size = args['network size']
        if size == 7:
            return datetime.timedelta(hours=12)
        elif size == 11:
            return datetime.timedelta(hours=12) #For 2000 runs
        elif size == 15:
            return datetime.timedelta(hours=15) #For 2000 runs
        elif size == 21:
            return datetime.timedelta(hours=18)
        elif size == 25:
            return datetime.timedelta(hours=18)
        else:
            raise RuntimeError("No time estimate for network sizes other than 11, 15, 21 or 25")

    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models,
            parameters.communication_models, parameters.fault_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods, parameters.slot_period, parameters.dissem_period,
            parameters.tdma_num_slots, parameters.slot_assignment_interval, parameters.minimum_setup_periods,
            parameters.pre_beacon_periods, parameters.search_distance,
            [parameters.timesync], parameters.timesync_periods
        ))

        # argument_product = list(itertools.product(
            # parameters.sizes, parameters.configurations,
            # parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            # [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            # parameters.source_periods, parameters.slot_periods, parameters.dissem_periods,
            # parameters.tdma_num_slots, parameters.slot_assignment_intervals, parameters.minimum_setup_periods,
            # parameters.pre_beacon_periods, parameters.dissem_timeouts, parameters.tdma_safety_periods_and_search_distances
        # ))

        # argument_product = [
                # (s, c, am, nm, cm, d, nido, lnst, src_period, sp, dp, ts, ai, msp, pbp, dt, sd, tsp)
            # for (s, c, am, nm, cm, d, nido, lnst, src_period, sp, dp, ts, ai, msp, pbp, dt, (tsp, sd))
            # in  argument_product
        # ]

        argument_product = self.add_extra_arguments(argument_product, extras)

        argument_product = self.adjust_source_period_for_multi_source(sim, argument_product)

        return argument_product

    # def _run_graph(self, args):
        # graph_parameters = {
            # 'normal latency': ('Normal Message Latency (ms)', 'left top'),
            # 'ssd': ('Sink-Source Distance (hops)', 'left top'),
            # 'captured': ('Capture Ratio (%)', 'left top'),
            # 'sent': ('Total Messages Sent', 'left top'),
            # 'received ratio': ('Receive Ratio (%)', 'left bottom'),
            # 'attacker distance': ('Meters', 'left top'),
        # }

        # # slp_tdma_das_results = results.Results(
            # # self.algorithm_module.result_file_path,
            # # parameters=self.algorithm_module.local_parameter_names,
            # # results=tuple(graph_parameters.keys()))

        # slp_tdma_das_results = results.Results(
            # "tossim",
            # self.algorithm_module.result_file_path("tossim"),
            # parameters=self.algorithm_module.local_parameter_names,
            # results=tuple(graph_parameters.keys()))

        # # for (vary, vary_prefix) in [("source period", " seconds"), ("attacker model", "")]:
        # for (vary, vary_prefix) in [("attacker model", "")]:
            # for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                # name = '{}-v-{}'.format(yaxis.replace(" ", "_"), vary.replace(" ", "-"))

                # g = versus.Grapher(
                    # "tossim",
                    # self.algorithm_module.graphs_path("tossim"), name,
                    # xaxis='network size', yaxis=yaxis, vary=vary,
                    # yextractor=scalar_extractor)

                # g.xaxis_label = 'Network Size'
                # g.yaxis_label = yaxis_label
                # g.vary_label = vary.title()
                # g.vary_prefix = vary_prefix
                # g.key_position = key_position

                # g.create(slp_tdma_das_results)

                # summary.GraphSummary(
                    # os.path.join(self.algorithm_module.graphs_path("tossim"), name),
                    # os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name))
                # ).run()

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'norm(sent,time taken)': ('Messages Sent per Second', 'left top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
            'path sent': ('Total Path Creation Messages Sent', 'left top'),
            'overhead': ('Path Creation Message Overhead', 'left top')
        }

        varying = [
                (('network size', ''), ('attacker model', ''))
                ]

        custom_yaxis_range_max = {
                'received ratio': 100,
                'overhead': 1,
                }

        self._create_versus_graph(args.sim, graph_parameters, varying,
                custom_yaxis_range_max=custom_yaxis_range_max,
                network_size_normalisation='UseNumNodes',
                no_key=True,
                generate_legend_graph=True)


    def _run_graph_versus_baseline(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'norm(sent,time taken)': ('Messages Sent per Second', 'left top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
        }

        varying = [
                (('network size', ''), ('search distance', ''))
                ]

        custom_yaxis_range_max = {
                'received ratio': 100,
                }

        print(dir(protectionless_tdma_das))

        self._create_baseline_versus_graph(args.sim, protectionless_tdma_das, graph_parameters, varying,
                custom_yaxis_range_max=custom_yaxis_range_max,
                network_size_normalisation='UseNumNodes',
                nokey=True,
                generate_legend_graph=True)

        # self._create_min_max_versus_graph(args.sim, [], protectionless_tdma_das, graph_parameters, varying,
                # custom_yaxis_range_max=custom_yaxis_range_max,
                # network_size_normalisation='UseNumNodes',
                # no_key=True,
                # generate_legend_graph=True)


    # def _run_graph_versus_baseline(self, args):
        # graph_parameters = {
            # 'normal latency': ('Normal Message Latency (ms)', 'left top'),
            # 'ssd': ('Sink-Source Distance (hops)', 'left top'),
            # 'captured': ('Capture Ratio (%)', 'left top'),
            # 'sent': ('Total Messages Sent', 'left top'),
            # 'received ratio': ('Receive Ratio (%)', 'left bottom'),
            # 'attacker distance': ('Meters', 'left top'),
            # 'norm(sent,time taken)': ('Messages Sent per Second', 'left top'),
            # 'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
        # }

        # protectionless_tdma_das_results = results.Results(
            # protectionless_tdma_das.result_file_path,
            # parameters=protectionless_tdma_das.local_parameter_names,
            # results=list(set(graph_parameters.keys()) & set(protectionless_tdma_das.Analysis.Analyzer.results_header().keys())))

        # slp_tdma_das_results = results.Results(
            # self.algorithm_module.result_file_path,
            # parameters=self.algorithm_module.local_parameter_names,
            # results=tuple(graph_parameters.keys()))

        # for (vary, vary_prefix) in [("source period", " seconds")]:
            # for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                # name = '{}-v-baseline-{}'.format(yaxis.replace(" ", "_"), vary.replace(" ", "-"))

                # g = baseline_versus.Grapher(
                    # self.algorithm_module.graphs_path, name,
                    # xaxis='network size', yaxis=yaxis, vary=vary,
                    # yextractor=scalar_extractor)

                # g.xaxis_label = 'Network Size'
                # g.yaxis_label = yaxis_label
                # g.vary_label = vary.title() + " -"
                # #g.vary_prefix = vary_prefix
                # g.key_position = key_position

                # g.force_vvalue_label = True
                # g.result_label = "SLP TDMA DAS"
                # g.baseline_label = "Protectionless TDMA DAS"

                # g.nokey = True
                # g.generate_legend_graph = True
                # g.legend_font_size = '8'

                # g.create(slp_tdma_das_results, baseline_results=protectionless_tdma_das_results)

                # summary.GraphSummary(
                    # os.path.join(self.algorithm_module.graphs_path, name),
                    # os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name))
                # ).run()

    # def _run_min_max_versus(self, args):
        # graph_parameters = {
            # 'normal latency': ('Normal Message Latency (ms)', 'left top'),
            # 'ssd': ('Sink-Source Distance (hops)', 'left top'),
            # 'captured': ('Capture Ratio (%)', 'left top'),
            # 'sent': ('Total Messages Sent', 'left top'),
            # 'received ratio': ('Receive Ratio (%)', 'left bottom'),
            # 'norm(sent,time taken)': ('Messages Sent per Second', 'left top'),
            # 'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
        # }

        # custom_yaxis_range_max = {
            # # 'sent': 450000,
            # # 'captured': 40,
            # 'received ratio': 100,
            # # 'normal latency': 300,
            # # 'norm(norm(sent,time taken),num_nodes)': 30,
        # }

        # protectionless_results = results.Results(
            # protectionless.result_file_path,
            # parameters=tuple(),
            # results=graph_parameters.keys(),
            # network_size_normalisation="UseNumNodes"
        # )

        # das_results = results.Results(
            # self.algorithm_module.result_file_path,
            # parameters=self.algorithm_module.local_parameter_names,
            # results=graph_parameters.keys(),
            # network_size_normalisation="UseNumNodes"
        # )

        # def graph_min_max_versus(result_name):
            # name = 'min-max-{}-versus-{}'.format(result_name, adaptive.name)

            # g = min_max_versus.Grapher(
                # self.algorithm_module.graphs_path, name,
                # xaxis='network size', yaxis=result_name, vary='search distance', yextractor=scalar_extractor)

            # # g.xaxis_label = 'Number of Nodes'
            # g.yaxis_label = graph_parameters[result_name][0]
            # g.key_position = graph_parameters[result_name][1]

            # g.nokey = True  # result_name in nokey

            # g.min_label = 'Dynamic - Lowest'
            # g.max_label = 'Dynamic - Highest'
            # g.comparison_label = 'DAS'
            # g.baseline_label = 'Protectionless - Baseline'
            # g.vary_label = ''

            # g.generate_legend_graph = True

            # g.point_size = 1.3
            # g.line_width = 4
            # g.yaxis_font = "',14'"
            # g.xaxis_font = "',12'"

            # if result_name in custom_yaxis_range_max:
                # g.yaxis_range_max = custom_yaxis_range_max[result_name]

            # g.vvalue_label_converter = lambda value: "W_h = {}".format(value)

            # g.create(das_results, protectionless_results)

            # summary.GraphSummary(
                # os.path.join(self.algorithm_module.graphs_path, name),
                # os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_"))
            # ).run()

        # for result_name in graph_parameters.keys():
            # graph_min_max_versus(result_name)
