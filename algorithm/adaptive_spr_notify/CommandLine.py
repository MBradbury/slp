from __future__ import print_function

from datetime import timedelta
import os.path

from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")
adaptive_spr = algorithm.import_algorithm("adaptive_spr")

from data import results

from data.table import fake_result

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.result_file_path)

        subparser = self._add_argument("table", self._run_table)
        subparser = self._add_argument("graph", self._run_graph)

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0

    def _cluster_time_estimator(self, args, **kwargs):
        historical_key_names = ('network size', 'source period')

        # Using the historical values from AdaptiveSPR
        historical = {
            (11, 0.125): timedelta(seconds=4),
            (11, 0.25): timedelta(seconds=5),
            (11, 0.5): timedelta(seconds=6),
            (11, 1.0): timedelta(seconds=6),
            (11, 2.0): timedelta(seconds=7),
            (15, 0.125): timedelta(seconds=20),
            (15, 0.25): timedelta(seconds=19),
            (15, 0.5): timedelta(seconds=21),
            (15, 1.0): timedelta(seconds=22),
            (15, 2.0): timedelta(seconds=27),
            (21, 0.125): timedelta(seconds=131),
            (21, 0.25): timedelta(seconds=108),
            (21, 0.5): timedelta(seconds=127),
            (21, 1.0): timedelta(seconds=114),
            (21, 2.0): timedelta(seconds=126),
            (25, 0.125): timedelta(seconds=367),
            (25, 0.25): timedelta(seconds=341),
            (25, 0.5): timedelta(seconds=307),
            (25, 1.0): timedelta(seconds=339),
            (25, 2.0): timedelta(seconds=356),
        }

        return self._cluster_time_estimator_from_historical(
            args, kwargs, historical_key_names, historical,
            allowance=0.3,
            max_time=timedelta(days=2)
        )



    def _run_table(self, args):
        adaptive_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=(
                'sent', 'delivered', 'time taken',
                'normal latency', 'ssd', 'captured',
                'fake', 'received ratio', 'tfs', 'pfs',
                'energy impact per node per second',
                #'norm(sent,time taken)', 'norm(norm(sent,time taken),network size)',
                #'norm(norm(norm(sent,time taken),network size),source rate)'
            ))

        result_table = fake_result.ResultTable(adaptive_results)

        self._create_table(self.algorithm_module.name + "-results", result_table)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'fake': ('Fake Messages Sent', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'tfs': ('Number of TFS Created', 'left top'),
            'pfs': ('Number of PFS Created', 'left top'),
            'tailfs': ('Number of TailFS Created', 'left top'),
            'attacker distance': ('Attacker Distance From Source (Meters)', 'left top'),
        }

        varying = [
            (('network size', ''), ('source period', ' seconds')),
            #(('network size', ''), ('communication model', '~')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
        }

        self._create_versus_graph(graph_parameters, varying, custom_yaxis_range_max)
