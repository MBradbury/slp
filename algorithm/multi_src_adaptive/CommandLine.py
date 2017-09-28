from __future__ import print_function

import os.path

from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

from data import results

from data.table import safety_period, fake_result, comparison
from data.graph import summary, versus, bar, min_max_versus
from data.util import useful_log10, scalar_extractor

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.name)

        subparser = self._subparsers.add_parser("table")
        subparser = self._subparsers.add_parser("graph")

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0


    def _run_table(self, args):
        adaptive_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=('normal latency', 'ssd', 'attacker distance'))

        result_table = fake_result.ResultTable(adaptive_results)

        self._create_table(self.algorithm_module.name + "-results", result_table)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'fake': ('Fake Messages Sent', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'tfs': ('Number of TFS Created', 'left top'),
            'pfs': ('Number of PFS Created', 'left top'),
            'attacker distance': ('Meters', 'left top'),
            'good move ratio': ('Good Move Ratio (%)', 'right top'),
            'norm(norm(sent,time taken),num_nodes)': ('Messages Sent per node per second', 'right top'),
        }

        adaptive_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation="NumSources")

        varying = [
            ("source period", " seconds"),
            ("communication model", "~")
        ]

        error_bars = set() # {'received ratio', 'good move ratio', 'norm(norm(sent,time taken),num_nodes)'}

        for (vary, vary_prefix) in varying:
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

                g.error_bars = yaxis in error_bars

                #g.nokey = True
                g.key_position = key_position

                g.create(adaptive_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    '{}-{}'.format(self.algorithm_module.name, name)
                ).run()

    def run(self, args):
        args = super(CLI, self).run(args)

        if 'table' == args.mode:
            self._run_table(args)

        if 'graph' == args.mode:
            self._run_graph(args)
