from __future__ import print_function

import itertools
import os
import datetime

import simulator.sim
from simulator import CommandLineCommon

import algorithm

from data import results, submodule_loader
from data.graph import summary, versus
from data.table import safety_period
from data.util import scalar_extractor

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        # super(CLI, self).__init__(__package__)
        super(CLI, self).__init__(None)

        subparser = self._add_argument("graph", self._run_graph)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser = self._add_argument("table", self._run_table)

    def _cluster_time_estimator(self, sim, args, **kwargs):
        return datetime.timedelta(hours=12)

    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models,
            parameters.communication_models, parameters.fault_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods, parameters.slot_period, parameters.dissem_period,
            parameters.tdma_num_slots, parameters.slot_assignment_interval, parameters.minimum_setup_periods,
            parameters.pre_beacon_periods, parameters.timesync, parameters.timesync_periods
        ))

        argument_product = self.add_extra_arguments(argument_product, extras)

        argument_product = self.adjust_source_period_for_multi_source(sim, argument_product)

        return argument_product

    def _run_table(self, args):
        print("NOTE: This table shows the average time taken to capture the source, not the safety period.")

        time_after_first_normal_to_safety_period = lambda tafn: tafn

        safety_period_table = safety_period.TableGenerator(
            self.algorithm_module.result_file_path,
            time_after_first_normal_to_safety_period
        )

        filename = f'{self.algorithm_module.name}-results'

        self._create_table(filename, safety_period_table)

    # def _run_graph(self, args):
        # graph_parameters = {
            # 'normal latency': ('Normal Message Latency (ms)', 'left top'),
            # 'ssd': ('Sink-Source Distance (hops)', 'left top'),
            # 'captured': ('Capture Ratio (%)', 'left top'),
            # 'sent': ('Total Messages Sent', 'left top'),
            # 'received ratio': ('Receive Ratio (%)', 'left bottom'),
            # 'attacker distance': ('Meters', 'left top'),
        # }

        # protectionless_tdma_das_results = results.Results(
            # self.algorithm_module.result_file_path,
            # parameters=self.algorithm_module.local_parameter_names,
            # results=tuple(graph_parameters.keys()))

        # for (vary, vary_prefix) in [("source period", " seconds")]:
            # for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                # name = '{}-v-{}'.format(yaxis.replace(" ", "_"), vary.replace(" ", "-"))

                # g = versus.Grapher(
                    # self.algorithm_module.graphs_path, name,
                    # xaxis='network size', yaxis=yaxis, vary=vary,
                    # yextractor=scalar_extractor)

                # g.xaxis_label = 'Network Size'
                # g.yaxis_label = yaxis_label
                # g.vary_label = vary.title()
                # g.vary_prefix = vary_prefix
                # g.key_position = key_position

                # g.create(protectionless_tdma_das_results)

                # summary.GraphSummary(
                    # os.path.join(self.algorithm_module.graphs_path, name),
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
        }

        varying = [
                (('network size', ''), ('attacker model', ''))
                ]

        custom_yaxis_range_max = {
                'received ratio': 100,
                }

        self._create_versus_graph(args.sim, graph_parameters, varying,
                custom_yaxis_range_max=custom_yaxis_range_max,
                network_size_normalisation='UseNumNodes',
                no_key=True,
                generate_legend_graph=True)

