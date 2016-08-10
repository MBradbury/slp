from __future__ import print_function

import os.path, itertools

from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

# The import statement doesn't work, so we need to use __import__ instead
template = __import__("algorithm.template", globals(), locals(), ['object'], -1)

from data import results

from data.table import safety_period, fake_result, comparison
from data.graph import summary, versus, bar, min_max_versus
from data.util import useful_log10, scalar_extractor

class CLI(CommandLineCommon.CLI):

    local_parameter_names = ('approach',)

    def __init__(self):
        super(CLI, self).__init__(__package__)

        subparser = self._subparsers.add_parser("table")
        subparser = self._subparsers.add_parser("graph")
        subparser = self._subparsers.add_parser("comparison-table")
        subparser = self._subparsers.add_parser("comparison-graph")
        subparser = self._subparsers.add_parser("min-max-versus")

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.source_periods, parameters.approaches
        ))

        return argument_product

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        if driver.mode() == "TESTBED":
            from data.run.common import RunTestbedCommon as RunSimulations
        else:
            from data.run.common import RunSimulationsCommon as RunSimulations

        safety_period_table_generator = safety_period.TableGenerator(protectionless.result_file_path)
        safety_periods = safety_period_table_generator.safety_periods()

        runner = RunSimulations(
            driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations, safety_periods=safety_periods)

        runner.run(self.algorithm_module.Parameters.repeats, self.parameter_names(), self._argument_product(), self._time_estimater)


    def _run_table(self, args):
        adaptive_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=('normal latency', 'ssd', 'attacker distance'))

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
            'attacker distance': ('Meters', 'left top'),
        }

        adaptive_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=tuple(graph_parameters.keys()))

        for (vary, vary_prefix) in [("source period", " seconds"), ("communication model", "~")]:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-{}'.format(yaxis.replace(" ", "_"), vary.replace(" ", "-"))

                yextractor = lambda x: scalar_extractor(x.get((0, 0), None)) if yaxis == 'attacker distance' else scalar_extractor(x)

                g = versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis='network size', yaxis=yaxis, vary=vary,
                    yextractor=yextractor)

                g.xaxis_label = 'Network Size'
                g.yaxis_label = yaxis_label
                g.vary_label = vary.title()
                g.vary_prefix = vary_prefix
                g.key_position = key_position

                g.create(adaptive_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    '{}-{}'.format(self.algorithm_module.name, name)
                ).run()


    def _run_comparison_table(self, args):
        results_to_compare = ('normal latency', 'ssd', 'captured',
                              'fake', 'received ratio', 'tfs', 'pfs')

        adaptive_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=results_to_compare)

        template_results = results.Results(
            template.result_file_path,
            parameters=('fake period', 'temp fake duration', 'pr(tfs)', 'pr(pfs)'),
            results=results_to_compare)

        result_table = comparison.ResultTable(template_results, adaptive_results)

        self._create_table("adaptive-template-comparison", result_table,
                           lambda (fp, dur, ptfs, ppfs): ptfs not in {0.2, 0.3, 0.4})

        self._create_table("adaptive-template-comparison-low-prob", result_table,
                           lambda (fp, dur, ptfs, ppfs): ptfs in {0.2, 0.3, 0.4})

    def _run_comparison_graph(self, args):
        results_to_compare = ('normal latency', 'ssd', 'captured', 'sent', 'received',
                              'normal', 'fake', 'away', 'choose', 'received ratio',
                              'tfs', 'pfs')

        adaptive_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
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
                extractor=lambda (diff, pcdiff): pcdiff if pc else diff
            ).create()

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_")
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
                extractor=lambda (diff, pcdiff): pcdiff if pc else diff,
                normalisor=normalisor)

            g.yaxis_label = 'Percentage Difference per Node' if pc else 'Average Difference per Node'
            if name_addition is not None:
                g.yaxis_label += ' ({})'.format(name_addition)

            g.xaxis_label = 'Parameters (P_{TFS}, D_{TFS}, Pr(TFS), Pr(PFS))'

            g.create()

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_")
            ).run()

        results_to_show = ('normal', 'fake', 'away', 'choose')

        create_comp_bar_pcdiff(pc=True,  shows=results_to_show)
        create_comp_bar_pcdiff(pc=False, shows=results_to_show)
        create_comp_bar_pcdiff(pc=True,  shows=results_to_show, modified=useful_log10, name_addition='log10')

    def _run_min_max_versus(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
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
            parameters=self.local_parameter_names,
            results=graph_parameters.keys())

        template_results = results.Results(
            template.result_file_path,
            parameters=template.CommandLine.CLI.local_parameter_names,
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

        if 'comparison-graph' == args.mode:
            self._run_comparison_graph(args)

        if 'min-max-versus' == args.mode:
            self._run_min_max_versus(args)
