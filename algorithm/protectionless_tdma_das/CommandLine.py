from __future__ import print_function

import itertools
import os

from simulator import CommandLineCommon

import algorithm

from data import results
from data.graph import summary, versus
from data.table import safety_period
from data.util import scalar_extractor

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__)

        subparser = self._add_argument("graph", self._run_graph)
        subparser = self._add_argument("table", self._run_table)

    def _argument_product(self, extras=None):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models,
            parameters.communication_models, parameters.fault_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods, parameters.slot_period, parameters.dissem_period,
            parameters.tdma_num_slots, parameters.slot_assignment_interval, parameters.minimum_setup_periods,
            parameters.pre_beacon_periods, parameters.dissem_timeout
        ))

        argument_product = self.add_extra_arguments(argument_product, extras)

        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product

    def _run_table(self, args):
        print("NOTE: This table shows the average time taken to capture the source, not the safety period.")

        time_after_first_normal_to_safety_period = lambda tafn: tafn

        safety_period_table = safety_period.TableGenerator(
            self.algorithm_module.result_file_path,
            time_after_first_normal_to_safety_period
        )

        filename = '{}-results'.format(self.algorithm_module.name)

        self._create_table(filename, safety_period_table)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'attacker distance': ('Meters', 'left top'),
        }

        protectionless_tdma_das_results = results.Results(
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

                g.create(protectionless_tdma_das_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name))
                ).run()
