from __future__ import print_function, division

from datetime import timedelta
import itertools
import os.path

from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")
template = algorithm.import_algorithm("template")

from data import results
from data.table import fake_result, comparison
from data.graph import summary, bar, min_max_versus
from data.util import useful_log10, scalar_extractor

safety_period_equivalence = {
    "attacker model": {"SeqNoReactiveAttacker()": "SeqNosReactiveAttacker()"}
}

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.name, safety_period_equivalence=safety_period_equivalence)

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("--show", action="store_true", default=False)

        subparser = self._add_argument("graph", self._run_graph)
        subparser = self._add_argument("comparison-table", self._run_comparison_table)
        subparser = self._add_argument("comparison-graph", self._run_comparison_graph)
        subparser = self._add_argument("min-max-versus", self._run_min_max_versus)

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0

    def _cluster_time_estimator(self, sim, args, **kwargs):
        historical_key_names = ('network size', 'source period')

        if sim == "tossim":
            historical = {
                (11, 0.125): timedelta(seconds=6),
                (11, 0.25): timedelta(seconds=8),
                (11, 0.5): timedelta(seconds=9),
                (11, 1.0): timedelta(seconds=10),
                (11, 2.0): timedelta(seconds=11),
                (15, 0.125): timedelta(seconds=25),
                (15, 0.25): timedelta(seconds=35),
                (15, 0.5): timedelta(seconds=46),
                (15, 1.0): timedelta(seconds=57),
                (15, 2.0): timedelta(seconds=62),
                (21, 0.125): timedelta(seconds=173),
                (21, 0.25): timedelta(seconds=446),
                (21, 0.5): timedelta(seconds=580),
                (21, 1.0): timedelta(seconds=513),
                (21, 2.0): timedelta(seconds=548),
                (25, 0.125): timedelta(seconds=747),
                (25, 0.25): timedelta(seconds=755),
                (25, 0.5): timedelta(seconds=2177),
                (25, 1.0): timedelta(seconds=1877),
                (25, 2.0): timedelta(seconds=1909),
            }
        else:
            historical = {}

        return self._cluster_time_estimator_from_historical(
            sim, args, kwargs, historical_key_names, historical,
            allowance=0.25,
            max_time=timedelta(days=2)
        )


    def _run_table(self, args):
        adaptive_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=(
                'sent', 'delivered', 'time taken',
                #'energy impact',
                #'energy impact per node',
                'energy impact per node per second',
                'captured', 'received ratio', #'ssd', 'attacker distance',
                'fake nodes at end', 'fake nodes at end when captured'
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
            'attacker distance': ('Meters', 'left top'),
            'norm(sent,time taken)': ('Total Messages Sent per Second', 'left top'),
        }

        varying = [
            (('network size', ''), ('source period', ' seconds')),
            #(('network size', ''), ('communication model', '~')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
        }

        self._create_versus_graph(graph_parameters, varying, custom_yaxis_range_max)


    def _run_comparison_table(self, args):
        results_to_compare = ('normal latency', 'ssd', 'captured',
                              'fake', 'received ratio', 'tfs', 'pfs')

        adaptive_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=results_to_compare)

        template_results = results.Results(
            template.result_file_path,
            parameters=('fake period', 'temp fake duration', 'pr(tfs)', 'pr(pfs)'),
            results=results_to_compare)

        result_table = comparison.ResultTable(template_results, adaptive_results)

        self._create_table("adaptive-template-comparison", result_table,
                           lambda x: x[2] not in {0.2, 0.3, 0.4}) #(fp, dur, ptfs, ppfs)

        self._create_table("adaptive-template-comparison-low-prob", result_table,
                           lambda x: x[2] in {0.2, 0.3, 0.4}) #(fp, dur, ptfs, ppfs)

    def _run_comparison_graph(self, args):
        results_to_compare = ('normal latency', 'ssd', 'captured', 'sent', 'received',
                              'normal', 'fake', 'away', 'choose', 'received ratio',
                              'tfs', 'pfs')

        adaptive_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=results_to_compare)

        template_results = results.Results(
            template.result_file_path,
            parameters=('fake period', 'temp fake duration', 'pr(tfs)', 'pr(pfs)'),
            results=results_to_compare)

        result_table = comparison.ResultTable(template_results, adaptive_results)

        def create_comp_bar(show, pc=False):
            name = 'template-comp-{}-{}'.format(show, "pcdiff" if pc else "diff")

            bar.DiffGrapher(
                self.algorithm_module.graphs_path, result_table, name,
                shows=[show],
                extractor=lambda x: x[1] if pc else x[0] #(diff, pcdiff)
            ).create()

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_"))
            ).run()

        for result_name in results_to_compare:
            create_comp_bar(result_name, pc=True)
            create_comp_bar(result_name, pc=False)

        def create_comp_bar_pcdiff(pc=True, modified=lambda x: x, name_addition=None, shows=results_to_compare):
            name = 'template-comp-{}'.format("pcdiff" if pc else "diff")
            if name_addition is not None:
                name += '-{}'.format(name_addition)

            # Normalise wrt to the number of nodes in the network
            def normalisor(key_names, key_values, params, yvalue):
                size = key_values[ key_names.index('size') ]
                result = yvalue / (size * size)

                return modified(result)

            g = bar.DiffGrapher(
                self.algorithm_module.graphs_path, result_table, name,
                shows=shows,
                extractor=lambda x: x[1] if pc else x[0], #(diff, pcdiff)
                normalisor=normalisor)

            g.yaxis_label = 'Percentage Difference per Node' if pc else 'Average Difference per Node'
            if name_addition is not None:
                g.yaxis_label += ' ({})'.format(name_addition)

            g.xaxis_label = 'Parameters (P_{TFS}, D_{TFS}, Pr(TFS), Pr(PFS))'

            g.create()

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_"))
            ).run()

        results_to_show = ('normal', 'fake', 'away', 'choose')

        create_comp_bar_pcdiff(pc=True,  shows=results_to_show)
        create_comp_bar_pcdiff(pc=False, shows=results_to_show)
        create_comp_bar_pcdiff(pc=True,  shows=results_to_show, modified=useful_log10, name_addition='log10')

    def _run_min_max_versus(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'fake': ('Fake Messages Sent', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'tfs': ('Number of TFS Created', 'left top'),
            'pfs': ('Number of PFS Created', 'left top'),
        }

        custom_yaxis_range_max = {
            'fake': 600000,
            'captured': 20
        }

        adaptive_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=graph_parameters.keys())

        template_results = results.Results(
            template.result_file_path,
            parameters=template.local_parameter_names,
            results=graph_parameters.keys())

        def graph_min_max_versus(result_name):
            name = 'min-max-{}-versus-{}'.format(template.name, result_name)

            g = min_max_versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='network size', yaxis=result_name, vary='approach', yextractor=scalar_extractor)

            g.xaxis_label = 'Network Size'
            g.yaxis_label = graph_parameters[result_name][0]
            g.key_position = graph_parameters[result_name][1]

            g.yaxis_font = g.xaxis_font = "',15'"

            g.nokey = True
            #g.key_font = "',20'"
            #g.key_spacing = "2"
            #g.key_width = "-5.5"

            g.point_size = '2'
            g.line_width = 2

            g.min_label = 'Static - Lowest'
            g.max_label = 'Static - Highest'
            g.comparison_label = 'Dynamic'
            g.vary_label = ''

            if result_name in custom_yaxis_range_max:
                g.yaxis_range_max = custom_yaxis_range_max[result_name]

            def vvalue_converter(name):
                return {
                    'PB_SINK_APPROACH': 'Pull Sink',
                    'PB_ATTACKER_EST_APPROACH': 'Pull Attacker'
                }[name]
            g.vvalue_label_converter = vvalue_converter

            g.generate_legend_graph = True

            g.create(template_results, adaptive_results)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_"))
            ).run()

        for result_name in graph_parameters.keys():
            graph_min_max_versus(result_name)
