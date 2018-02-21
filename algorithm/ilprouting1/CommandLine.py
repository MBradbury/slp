from __future__ import print_function

import itertools
import os

import simulator.sim
from simulator.Simulation import Simulation
from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")

from data import results, latex, submodule_loader
from data.table import safety_period, direct_comparison, fake_result
from data.graph import summary, versus
from data.util import scalar_extractor

# Use the safety periods for SeqNosReactiveAttacker() if none are available for SeqNosOOOReactiveAttacker()
safety_period_equivalence = {
    "attacker model": {"SeqNosOOOReactiveAttacker()": "SeqNosReactiveAttacker()"}
}

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(protectionless.name, safety_period_equivalence=safety_period_equivalence)

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--show", action="store_true", default=False)

        subparser = self._add_argument("graph", self._run_graph)

    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        parameter_values = self._get_global_parameter_values(sim, parameters)
        parameter_values.append(parameters.buffer_sizes)
        parameter_values.append(parameters.max_walk_lengths)
        parameter_values.append(parameters.direct_to_sink_prs)
        parameter_values.append(parameters.msg_group_sizes)

        argument_product = list(itertools.product(*parameter_values))

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

        self._create_results_table(args.sim, parameters, show=args.show)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
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
            xaxis_font = "',16'",
            yaxis_font = "',16'",
            xlabel_font = "',18'",
            ylabel_font = "',18'",
            line_width = 3,
            point_size = 2,
            nokey = True,
            generate_legend_graph = True,
            legend_font_size = 16,
        )

    def run(self, args):
        args = super(CLI, self).run(args)

        if 'table' == args.mode:
            self._run_table(args)

        if 'graph' == args.mode:
            self._run_graph(args)

