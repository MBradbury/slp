from __future__ import print_function

from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")
protectionless_ctp = algorithm.import_algorithm("protectionless_ctp")
adaptive_spr = algorithm.import_algorithm("adaptive_spr")

from data import results

from data.table import fake_result

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless_ctp.result_file_path)

        subparser = self._add_argument("table", self._run_table)
        subparser = self._add_argument("graph", self._run_graph)
        subparser = self._add_argument("graph-baseline", self._run_graph_baseline)
        subparser = self._add_argument("graph-min-max", self._run_graph_min_max)

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0


    def _run_table(self, args):
        algo_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=(
                #'sent', 'time taken',
                'normal latency', 'ssd', 'captured',
                'fake', 'received ratio', 'tfs', 'pfs', 'tailfs'
                #'norm(sent,time taken)', 'norm(norm(sent,time taken),network size)',
                #'norm(norm(norm(sent,time taken),network size),source rate)'
            ))

        result_table = fake_result.ResultTable(algo_results)

        self._create_table(self.algorithm_module.name + "-results", result_table)

    @staticmethod
    def vvalue_converter(name):
        return {
            "PB_FIXED1_APPROACH": "Fixed1",
            "PB_FIXED2_APPROACH": "Fixed2",
            "PB_RND_APPROACH": "Rnd",
        }[name]

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
            (('network size', ''), ('source period', ' seconds')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
        }

        self._create_versus_graph(graph_parameters, varying, custom_yaxis_range_max)

    def _run_graph_baseline(self, args):
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
            #(('network size', ''), ('source period', ' seconds')),
            (('network size', ''), ('approach', '')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
        }

        self._create_baseline_versus_graph(adaptive_spr, graph_parameters, varying, custom_yaxis_range_max)

    def _run_graph_min_max(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            #'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'norm(sent,time taken)': ('Total Messages Sent per Second', 'left top'),
        }

        varying = [
            #(('network size', ''), ('source period', ' seconds')),
            (('network size', ''), ('approach', '')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
        }

        self._create_min_max_versus_graph(
            [protectionless_ctp, protectionless, adaptive_spr], None, graph_parameters, varying, custom_yaxis_range_max,
            min_label=['CTP - Lowest', 'Flooding - Lowest', "SPR - Lowest"],
            max_label=['CTP - Highest', 'Flooding - Highest', "SPR - Highest"],
            vary_label="",
            comparison_label='SPR CTP',
            vvalue_label_converter=self.vvalue_converter,
        )
