from __future__ import print_function

import os.path

from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")
adaptive = algorithm.import_algorithm("adaptive")
adaptive_spr = algorithm.import_algorithm("adaptive_spr")

from data import results

from data.table import fake_result, comparison
from data.graph import summary, versus, min_max_versus
from data.util import scalar_extractor

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.result_file_path)

        subparser = self._subparsers.add_parser("table")
        subparser = self._subparsers.add_parser("graph")
        subparser = self._subparsers.add_parser("comparison-table")
        subparser = self._subparsers.add_parser("min-max-versus")

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0


    def _run_table(self, args):
        adaptive_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=(
                #'sent', 'time taken',
                'normal latency', 'ssd', 'captured',
                'fake', 'dummy normal', 'received ratio', 'tfs', 'pfs', 'tailfs'
                #'norm(sent,time taken)', 'norm(norm(sent,time taken),network size)',
                #'norm(norm(norm(sent,time taken),network size),source rate)'
            ))

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
            'tailfs': ('Number of TailFS Created', 'left top'),
            'attacker distance': ('Meters', 'left top'),
        }

        adaptive_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()))

        for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
            name = '{}-v-source-period'.format(yaxis.replace(" ", "_"))

            g = versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='network size', yaxis=yaxis, vary='source period',
                yextractor=scalar_extractor)

            g.xaxis_label = 'Network Size'
            g.yaxis_label = yaxis_label
            g.vary_label = 'Source Period'
            g.vary_prefix = ' seconds'
            g.key_position = key_position

            g.create(adaptive_results)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name)
            ).run()

    def _run_comparison_table(self, args):
        results_to_compare = ('normal latency', 'ssd', 'captured',
                              'fake', 'received ratio', 'tfs', 'pfs')

        our_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=results_to_compare)

        adaptive_spr_results = results.Results(
            adaptive_spr.result_file_path,
            parameters=('fake period', 'temp fake duration', 'pr(tfs)', 'pr(pfs)'),
            results=results_to_compare)

        result_table = comparison.ResultTable(adaptive_spr_results, our_results)

        self._create_table("{}-{}-comparison".format(self.algorithm_module.name, adaptive_spr.name), result_table)

    def _run_min_max_versus(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'normal': ('Normal Messages Sent', 'left top'),
            'fake': ('Fake Messages Sent', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'tfs': ('Number of TFS Created', 'left top'),
            'pfs': ('Number of PFS Created', 'left top'),
            'attacker distance': ('meters', 'left top'),
            'norm(sent,time taken)': ('Messages Sent per Second', 'left top'),
            'norm(fake,time taken)': ('Messages Sent per Second', 'left top'),
            'norm(normal,time taken)': ('Messages Sent per Second', 'left top'),
            'norm(norm(fake,time taken),source rate)': ('~', 'left top'),
        }

        custom_yaxis_range_max = {
            'fake': 400000,
            'captured': 10,
            'received ratio': 100,
            'attacker distance': 120,
            'normal latency': 200,
            'pfs': 30,
            'tfs': 500,
            'norm(sent,time taken)': 12000,
            'norm(fake,time taken)': 12000,
            'norm(normal,time taken)': 3500,
            'ssd': 30,
        }

        protectionless_results = results.Results(
            protectionless.result_file_path,
            parameters=protectionless.CommandLine.CLI.parameter_names,
            results=list(set(graph_parameters.keys()) - {'tfs', 'pfs', 'fake', 'norm(fake,time taken)',
                                                         'norm(norm(fake,time taken),source rate)'})
        )

        our_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=graph_parameters.keys())

        adaptive_spr_results = results.Results(
            adaptive.result_file_path,
            parameters=adaptive.CommandLine.CLI.parameter_names,
            results=graph_parameters.keys())

        def graph_min_max_versus(result_name):
            name = 'min-max-{}-versus-{}'.format(adaptive.name, result_name)

            yextractor = lambda x: scalar_extractor(x.get((0, 0), None)) if result_name == 'attacker distance' else scalar_extractor(x)

            g = min_max_versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='network size', yaxis=result_name, vary='approach', yextractor=yextractor)

            g.xaxis_label = 'Network Size'
            g.yaxis_label = graph_parameters[result_name][0]
            g.key_position = graph_parameters[result_name][1]

            g.yaxis_font = g.xaxis_font = "',15'"

            g.nokey = True
            #g.key_font = "',20'"
            #g.key_spacing = "2"
            #g.key_width = "+6"

            g.point_size = '2'
            g.line_width = 4

            g.min_label = 'Dynamic - Lowest'
            g.max_label = 'Dynamic - Highest'
            g.comparison_label = 'DynamicSpr'
            g.vary_label = ''

            if result_name in custom_yaxis_range_max:
                g.yaxis_range_max = custom_yaxis_range_max[result_name]

            def vvalue_converter(name):
                return {
                    "PB_FIXED1_APPROACH": "Fixed1",
                    "PB_FIXED2_APPROACH": "Fixed2",
                    "PB_RND_APPROACH": "Rnd",
                }[name]
            g.vvalue_label_converter = vvalue_converter

            g.generate_legend_graph = True

            if result_name in protectionless_results.result_names:
                g.create(adaptive_spr_results, our_results, baseline_results=protectionless_results)
            else:
                g.create(adaptive_spr_results, our_results)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_")
            ).run()

        for result_name in graph_parameters.keys():
            graph_min_max_versus(result_name)

    def run(self, args):
        args = super(CLI, self).run(args)

        if 'table' == args.mode:
            self._run_table(args)

        if 'graph' == args.mode:
            self._run_graph(args)

        if 'comparison-table' == args.mode:
            self._run_comparison_table(args)

        if 'min-max-versus' == args.mode:
            self._run_min_max_versus(args)
