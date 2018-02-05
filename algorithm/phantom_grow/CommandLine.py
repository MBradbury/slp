from __future__ import print_function, division

import itertools
import os.path

from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

from data import results

from data.table import safety_period, fake_result
from data.graph import summary, versus
from data.util import scalar_extractor

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(protectionless.name)

        subparser = self._subparsers.add_parser("table")
        subparser = self._subparsers.add_parser("graph")

    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.ifilter(
            lambda (size, c, am, nm, cm, d, nido, lnst, sp, walk_length): walk_length in parameters.walk_hop_lengths[size],
            itertools.product(
                parameters.sizes, parameters.configurations,
                parameters.attacker_models, parameters.noise_models, parameters.communication_models,
                [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
                parameters.source_periods,
                set(itertools.chain(*parameters.walk_hop_lengths.values()))
            )
        ))

        argument_product = self.add_extra_arguments(argument_product, extras)

        return argument_product


    def _run_table(self, args):
        phantom_results = results.Results(self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'sent', 'received ratio', 'paths reached end'))

        result_table = fake_result.ResultTable(phantom_results)

        self._create_table(self.algorithm_module.name + "-results", result_table)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'paths reached end': ('Paths Reached End (%)', 'right top'),
        }

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys())
        )

        parameters = [
            ('source period', ' seconds'),
            ('walk length', ' hops')
        ]

        for (parameter_name, parameter_unit) in parameters:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-{}'.format(yaxis.replace(" ", "_"), parameter_name.replace(" ", "-"))

                g = versus.Grapher(self.algorithm_module.graphs_path, name,
                    xaxis='network size', yaxis=yaxis, vary=parameter_name, yextractor=scalar_extractor)

                g.xaxis_label = 'Network Size'
                g.yaxis_label = yaxis_label
                g.vary_label = parameter_name.title()
                g.vary_prefix = parameter_unit
                g.key_position = key_position

                g.create(phantom_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    self.algorithm_module.name + '-' + name
                ).run()

    def run(self, args):
        args = super(CLI, self).run(args)

        if 'table' == args.mode:
            self._run_table(args)

        if 'graph' == args.mode:
            self._run_graph(args)
