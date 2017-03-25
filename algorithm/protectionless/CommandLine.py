from __future__ import print_function

import datetime
import itertools
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

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods
        )

        # Factor in the number of sources when selecting the source period.
        # This is done so that regardless of the number of sources the overall
        # network's normal message generation rate is the same.
        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product

    def _cluster_time_estimator(self, args, **kwargs):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        size = args['network size']
        if size == 11:
            return datetime.timedelta(hours=9)
        elif size == 15:
            return datetime.timedelta(hours=21)
        elif size == 21:
            return datetime.timedelta(hours=42)
        elif size == 25:
            return datetime.timedelta(hours=71)
        else:
            raise RuntimeError("No time estimate for network sizes other than 11, 15, 21 or 25")

    def _run_table(self, args):
        protectionless_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=(
                'sent', 'delivered', 'time taken',
                #'energy impact',
                #'energy impact per node',
                'energy impact per node per second',
                'norm(norm(sent,time taken),num_nodes)',
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
            'norm(norm(sent,time taken),num_nodes)': ('Messages Sent per node per second', 'right top'),
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
                yextractor=lambda (diff, pcdiff): pcdiff if pc else diff
            ).create(result_table)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_")
            ).run()

        for result_name in result_names:
            create_ccpe_comp_versus(result_name, pc=True)
            create_ccpe_comp_versus(result_name, pc=False)
