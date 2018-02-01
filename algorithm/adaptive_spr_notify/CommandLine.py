from __future__ import print_function

from datetime import timedelta
import os.path

from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")
adaptive = algorithm.import_algorithm("adaptive")
template = algorithm.import_algorithm("template")
#adaptive_spr = algorithm.import_algorithm("adaptive_spr")

from data import results
from data.table import fake_result
from data.graph import summary, min_max_versus
from data.util import scalar_extractor

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.name)

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("--show", action="store_true", default=False)
        
        subparser = self._add_argument("graph", self._run_graph)
        subparser = self._add_argument("min-max-versus", self._run_min_max_versus)

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0

    def _cluster_time_estimator(self, sim, args, **kwargs):
        historical_key_names = ('network size', 'source period')

        if sim == "tossim":
            # Using the historical values from AdaptiveSPR
            # Using size 11 network's time for size 7
            historical = {
                (7, 0.125): timedelta(seconds=4),
                (7, 0.25): timedelta(seconds=5),
                (7, 0.5): timedelta(seconds=6),
                (7, 1.0): timedelta(seconds=6),
                (7, 2.0): timedelta(seconds=7),
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
        else:
            historical = {}

        return self._cluster_time_estimator_from_historical(
            sim, args, kwargs, historical_key_names, historical,
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

        self._create_table(self.algorithm_module.name + "-results", result_table, show=args.show)

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


    def _run_min_max_versus(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
#            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
#            'normal': ('Normal Messages Sent', 'left top'),
            'fake': ('Fake Messages Sent', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
#            'tfs': ('Number of TFS Created', 'left top'),
#            'pfs': ('Number of PFS Created', 'left top'),
            'attacker distance': ('Attacker Distance From Source (meters)', 'left top'),
            #'norm(sent,time taken)': ('Messages Sent per Second', 'left top'),
            #'norm(fake,time taken)': ('Messages Sent per Second', 'left top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
            'norm(norm(fake,time taken),network size)': ('Fake Messages Sent per Second per node', 'left top'),
#            'norm(normal,time taken)': ('Messages Sent per Second', 'left top'),
#            'norm(norm(fake,time taken),source rate)': ('~', 'left top'),
#            #'energy impact per node': ('Energy Impact per Node (mAh)', 'left top'),
            'energy impact per node per second': ('Energy Impact per Node per Second (mAh s^{-1})', 'left top'),
            'energy allowance used': ('Energy Allowance Used (\\%)', 'left top'),
        }

        custom_yaxis_range_max = {
            'captured': 6,
            'received ratio': 100,
            'attacker distance': 140,
            'normal latency': 200,
            'norm(norm(sent,time taken),network size)': 7,
            'norm(norm(fake,time taken),network size)': 7,
            #'energy impact per node per second': 0.0003,
            #'energy allowance used': 100,
        }

        def filter_params(all_params):
            return all_params['source period'] == '0.125' or all_params['noise model'] == 'casino-lab'

        protectionless_results = results.Results(
            protectionless.result_file_path,
            parameters=protectionless.local_parameter_names,
            results=list(set(graph_parameters.keys()) & set(protectionless.Analysis.Analyzer.results_header().keys())),
            results_filter=filter_params)

        adaptive_spr_notify_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=graph_parameters.keys(),
            results_filter=filter_params)

        adaptive_results = results.Results(
            adaptive.result_file_path,
            parameters=adaptive.local_parameter_names,
            results=graph_parameters.keys(),
            results_filter=filter_params)

        template_results = results.Results(
            template.result_file_path,
            parameters=template.local_parameter_names,
            results=graph_parameters.keys(),
            results_filter=filter_params)

        def graph_min_max_versus(result_name, xaxis):
            name = 'min-max-{}-versus-{}-{}'.format(adaptive.name, result_name, xaxis)

            if result_name == "attacker distance":
                # Just get the distance of attacker 0 from node 0 (the source in SourceCorner)
                def yextractor(yvalue):
                    print(yvalue)
                    return scalar_extractor(yvalue)[(0, 0)]
            else:
                yextractor = scalar_extractor

            g = min_max_versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis=xaxis, yaxis=result_name, vary='approach', yextractor=yextractor)

            g.xaxis_label = xaxis.title()
            g.yaxis_label = graph_parameters[result_name][0]
            g.key_position = graph_parameters[result_name][1]

            g.yaxis_font = g.xaxis_font = "',15'"

            g.nokey = True
            #g.key_font = "',20'"
            #g.key_spacing = "2"
            #g.key_width = "+6"

            g.point_size = '2'
            g.line_width = 2

            g.min_label = ['Dynamic - Lowest', 'Static - Lowest']
            g.max_label = ['Dynamic - Highest', 'Static - Highest']
            g.comparison_label = 'DynamicSpr'
            g.vary_label = ''

            if result_name in custom_yaxis_range_max:
                g.yaxis_range_max = custom_yaxis_range_max[result_name]

            def vvalue_converter(name):
                try:
                    return {
                        "PB_FIXED1_APPROACH": "Fixed1",
                        "PB_FIXED2_APPROACH": "Fixed2",
                        "PB_RND_APPROACH": "Rnd",
                    }[name]
                except KeyError:
                    return name
            g.vvalue_label_converter = vvalue_converter

            g.generate_legend_graph = True

            if result_name in protectionless_results.result_names:
                g.create([adaptive_results, template_results], adaptive_spr_notify_results, baseline_results=protectionless_results)
            else:
                g.create([adaptive_results, template_results], adaptive_spr_notify_results)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_"))
            ).run()

        for result_name in graph_parameters.keys():
            graph_min_max_versus(result_name, 'network size')
