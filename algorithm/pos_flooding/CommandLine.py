from __future__ import print_function

import datetime
import os

import algorithm
protectionless = algorithm.import_algorithm("protectionless")

from simulator.Simulation import Simulation
from simulator import CommandLineCommon

from data import results
from data.table import safety_period, direct_comparison, fake_result
from data.table.data_formatter import TableDataFormatter
from data.graph import summary, versus
from data.util import scalar_extractor

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.name)

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("--show-stddev", action="store_true")
        subparser.add_argument("--show", action="store_true", default=False)

        subparser = self._add_argument("graph", self._run_graph)

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0

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
                'sent', 'captured', 'received ratio',
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
            #'norm(norm(sent,time taken),num_nodes)': ('Messages Sent per node per second', 'right top'),
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
