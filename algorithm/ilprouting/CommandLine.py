from __future__ import print_function

import itertools

from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")

from data import results
from data.table import fake_result

# Use the safety periods for SeqNosReactiveAttacker() if none are available for SeqNosOOOReactiveAttacker()
safety_period_equivalence = {
    "attacker model": {"SeqNosOOOReactiveAttacker()": "SeqNosReactiveAttacker()"}
}

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.name, safety_period_equivalence=safety_period_equivalence)

        subparser = self._add_argument("table", self._run_table)
        subparser = self._add_argument("graph", self._run_graph)

    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models,
            parameters.communication_models, parameters.fault_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods, parameters.buffer_sizes, parameters.max_walk_lengths,
            parameters.direct_to_sink_prs, parameters.msg_group_sizes
        ))

        argument_product = self.add_extra_arguments(argument_product, extras)
        
        return argument_product

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0

    def _run_table(self, args):
        parameters = [
            'normal latency', 'ssd', 'captured',
            'received ratio', 'failed avoid sink',
            'failed avoid sink when captured',
        ]

        self._create_results_table(args.sim, parameters)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            #'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            #'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'norm(sent,time taken)': ('Total Messages Sent per Second', 'left top'),
            #'failed avoid sink': ('Failed to Avoid Sink (%)', 'left top'),
            #'failed avoid sink when captured': ('Failed to Avoid Sink When Captured (%)', 'left top'),
        }

        varying = [
            (('network size', ''), ('msg group size', '')),
            #(('network size', ''), ('source period', ' seconds')),
            #(('network size', ''), ('pr direct to sink', '')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
            'norm(sent,time taken)': 300,
            'captured': 9,
            'normal latency': 4000,
        }

        self._create_versus_graph(graph_parameters, varying, custom_yaxis_range_max,
            xaxis_font = "',18'",
            yaxis_font = "',18'",
            xlabel_font = "',17'",
            ylabel_font = "',17'",
            line_width = 3,
            point_size = 2,
            nokey = True,
            generate_legend_graph = True,
            legend_font_size = 16,
        )
