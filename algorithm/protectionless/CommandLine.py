from __future__ import print_function

from datetime import timedelta
import os

import algorithm

from simulator.Simulation import Simulation
from simulator import CommandLineCommon

from data import results
from data.table import safety_period, direct_comparison, fake_result
from data.table.data_formatter import TableDataFormatter
from data.graph import summary, versus
from data.util import scalar_extractor

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__)

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("--show-stddev", action="store_true")
        subparser.add_argument("--show", action="store_true", default=False)

        subparser = self._add_argument("graph", self._run_graph)
        subparser = self._add_argument("ccpe-comparison-table", self._run_ccpe_comparison_table)
        subparser = self._add_argument("ccpe-comparison-graph", self._run_ccpe_comparison_graphs)

    def _cluster_time_estimator(self, args, **kwargs):
        historical_key_names = ('network size', 'source period')
        historical = {
            ('11', '0.125'): timedelta(seconds=2),
            ('11', '0.25'): timedelta(seconds=2),
            ('11', '0.5'): timedelta(seconds=2),
            ('11', '1.0'): timedelta(seconds=3),
            ('11', '2.0'): timedelta(seconds=3),
            ('15', '0.125'): timedelta(seconds=6),
            ('15', '0.25'): timedelta(seconds=6),
            ('15', '0.5'): timedelta(seconds=7),
            ('15', '1.0'): timedelta(seconds=8),
            ('15', '2.0'): timedelta(seconds=9),
            ('21', '0.125'): timedelta(seconds=31),
            ('21', '0.25'): timedelta(seconds=29),
            ('21', '0.5'): timedelta(seconds=32),
            ('21', '1.0'): timedelta(seconds=32),
            ('21', '2.0'): timedelta(seconds=34),
            ('25', '0.125'): timedelta(seconds=71),
            ('25', '0.25'): timedelta(seconds=70),
            ('25', '0.5'): timedelta(seconds=73),
            ('25', '1.0'): timedelta(seconds=82),
            ('25', '2.0'): timedelta(seconds=70),
        }

        return self._cluster_time_estimator_from_historical(
            args, kwargs, historical_key_names, historical,
            allowance=0.25
        )

    def _run_table(self, args):
        protectionless_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=(
                'sent', 'delivered', 'time taken',
                #'energy impact',
                #'energy impact per node',
                #'energy impact per node per second',
                'norm(norm(sent,time taken),network size)',
                'normal latency', 'ssd', 'attacker distance',
            ))

        fmt = TableDataFormatter(convert_to_stddev=args.show_stddev)

        result_table = fake_result.ResultTable(protectionless_results, fmt)

        self._create_table(self.algorithm_module.name + "-results", result_table, show=args.show)

    def _run_graph(self, args):
        graph_parameters = {
            'time taken': ('Time Taken (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            #'good move ratio': ('Good Move Ratio (%)', 'right top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per node per second', 'right top'),
        }

        varying = [
            (('network size', ''), ('source period', ' seconds')),
            (('network size', ''), ('communication model', '~')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
        }

        self._create_versus_graph(graph_parameters, varying, custom_yaxis_range_max,
            source_period_normalisation="NumSources"
        )

    def _run_ccpe_comparison_table(self, args):
        from data.old_results import OldResults

        old_results = OldResults(
            'results/CCPE/protectionless-results.csv',
            parameters=tuple(),
            results=('time taken', 'received ratio', 'safety period')
        )

        protectionless_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=('time taken', 'received ratio', 'safety period')
        )

        result_table = direct_comparison.ResultTable(old_results, protectionless_results)

        self._create_table('{}-ccpe-comparison'.format(self.algorithm_module.name), result_table)

    def _run_ccpe_comparison_graphs(self, args):
        from data.old_results import OldResults

        result_names = ('time taken', 'received ratio', 'safety period')

        old_results = OldResults(
            'results/CCPE/protectionless-results.csv',
            parameters=self.algorithm_module.local_parameter_names,
            results=result_names
        )

        protectionless_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=result_names
        )

        result_table = direct_comparison.ResultTable(old_results, protectionless_results)

        def create_ccpe_comp_versus(yxaxis, pc=False):
            name = 'ccpe-comp-{}-{}'.format(yxaxis, "pcdiff" if pc else "diff")

            versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='network size', yaxis=yxaxis, vary='source period',
                yextractor=lambda diff, pcdiff: pcdiff if pc else diff
            ).create(result_table)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_")
            ).run()

        for result_name in result_names:
            create_ccpe_comp_versus(result_name, pc=True)
            create_ccpe_comp_versus(result_name, pc=False)
