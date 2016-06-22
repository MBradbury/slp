from __future__ import print_function

import os, itertools

from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

# The import statement doesn't work, so we need to use __import__ instead
adaptive = __import__("algorithm.adaptive", globals(), locals(), ['object'], -1)

from data import results

from data.table import safety_period, fake_result
from data.graph import summary, versus, min_max_versus, dual_min_max_versus
from data.util import scalar_extractor

from data.run.common import RunSimulationsCommon as RunSimulations

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    noise_models = ["meyer-heavy", "casino-lab"]

    communication_models = ["no-asymmetry", "high-asymmetry", "ideal"]

    sizes = [11, 15, 21, 25]

    source_periods = [1.0, 0.5, 0.25, 0.125]

    configurations = [
        'SourceCorner',
        #'SinkCorner',
        #'FurtherSinkCorner',
        #'Generic1',
        #'Generic2',
        
        #'RingTop',
        #'RingOpposite',
        #'RingMiddle',
        
        #'CircleEdges',
        #'CircleSourceCentre',
        #'CircleSinkCentre',

        #'Source2Corners',
    ]

    attacker_models = ['SeqNoReactiveAttacker()']

    walk_hop_lengths = {11: [6, 10, 14], 15: [10, 14, 18], 21: [16, 20, 24], 25: [20, 24, 28]}

    landmark_nodes = ['sink_id', 'bottom_right']

    repeats = 500

    local_parameter_names = ('walk length', 'landmark node')


    def __init__(self):
        super(CLI, self).__init__(__package__)

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        safety_period_table_generator = safety_period.TableGenerator(protectionless.result_file_path)
        safety_periods = safety_period_table_generator.safety_periods()

        runner = RunSimulations(driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations, safety_periods=safety_periods)

        argument_product = list(itertools.ifilter(
            lambda (size, _1, _2, _3, _4, _5, _6, walk_length, _7): walk_length in self.walk_hop_lengths[size],
            itertools.product(
                self.sizes, self.configurations,
                self.attacker_models, self.noise_models, self.communication_models,
                [self.distance], self.source_periods,
                set(itertools.chain(*self.walk_hop_lengths.values())), self.landmark_nodes)
        ))

        runner.run(self.executable_path, self.repeats, self.parameter_names(), argument_product)


    def _run_table(self, args):
        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'sent', 'received ratio', 'paths reached end', 'source dropped'))

        result_table = fake_result.ResultTable(phantom_results)

        self._create_table("{}-results".format(self.algorithm_module.name), result_table)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'paths reached end': ('Paths Reached End (%)', 'right top'),
            'source dropped': ('Source Dropped Messages (%)', 'right top'),
        }

        custom_yaxis_range_max = {
            'source dropped': 100,
            'paths reached end': 100,
        }

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            network_size_normalisation="UseNumNodes"
        )

        parameters = [
            ('source period', ' seconds'),
            ('walk length', ' hops')
        ]

        for (parameter_name, parameter_unit) in parameters:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-{}'.format(yaxis.replace(" ", "_"), parameter_name.replace(" ", "-"))

                g = versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis='network size', yaxis=yaxis, vary=parameter_name,
                    yextractor=scalar_extractor
                )

                g.xaxis_label = 'Number of Nodes'
                g.yaxis_label = yaxis_label
                g.vary_label = parameter_name.title()
                g.vary_prefix = parameter_unit
                g.key_position = key_position

                g.nokey = True

                g.generate_legend_graph = True

                g.point_size = 1.3
                g.line_width = 4
                g.yaxis_font = "',14'"
                g.xaxis_font = "',12'"

                if yaxis in custom_yaxis_range_max:
                    g.yaxis_range_max = custom_yaxis_range_max[yaxis]

                g.create(phantom_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    self.algorithm_module.name + '-' + name
                ).run()

    def _run_min_max_versus(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'at 17.5,290'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'norm(norm(sent,time taken),num_nodes)': ('Total Messages Sent per node per second', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'right top'),
            'energy impact per node per second': ('Energy Impact per Node per second (mAh s^{-1})', 'left top'),
            'energy allowance used': ('Energy Allowance Used (\%)', 'left top'),
        }

        custom_yaxis_range_max = {
            'sent': 450000,
            'captured': 40,
            'received ratio': 100,
            'normal latency': 300,
            'norm(norm(sent,time taken),num_nodes)': 30,
            'energy allowance used': 100,
        }

        nokey = {'captured', 'sent', 'received ratio',
                 'norm(norm(sent,time taken),num_nodes)', 'energy allowance used'}

        protectionless_results = results.Results(
            protectionless.result_file_path,
            parameters=tuple(),
            results=graph_parameters.keys(),
            network_size_normalisation="UseNumNodes"
        )

        adaptive_results = results.Results(
            adaptive.result_file_path,
            parameters=('approach',),
            results=graph_parameters.keys(),
            network_size_normalisation="UseNumNodes"
        )

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=graph_parameters.keys(),
            network_size_normalisation="UseNumNodes"
        )

        def graph_min_max_versus(result_name):
            name = 'min-max-{}-versus-{}'.format(result_name, adaptive.name)

            g = min_max_versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='network size', yaxis=result_name, vary='walk length', yextractor=scalar_extractor)

            g.xaxis_label = 'Number of Nodes'
            g.yaxis_label = graph_parameters[result_name][0]
            g.key_position = graph_parameters[result_name][1]

            g.nokey = result_name in nokey

            g.min_label = 'Dynamic - Lowest'
            g.max_label = 'Dynamic - Highest'
            g.comparison_label = 'Phantom'
            g.baseline_label = 'Protectionless - Baseline'
            g.vary_label = ''

            g.generate_legend_graph = True

            g.point_size = 1.3
            g.line_width = 4
            g.yaxis_font = "',14'"
            g.xaxis_font = "',12'"

            if result_name in custom_yaxis_range_max:
                g.yaxis_range_max = custom_yaxis_range_max[result_name]

            g.vvalue_label_converter = lambda value: "W_h = {}".format(value)

            g.create(adaptive_results, phantom_results, protectionless_results)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_")
            ).run()

        for result_name in graph_parameters.keys():
            graph_min_max_versus(result_name)

    def _run_dual_min_max_versus(self, args):
        graph_parameters = {
            ('norm(norm(sent,time taken),num_nodes)', 'energy allowance used'): ('Total Messages Sent per node per second', 'Energy Allowance Used (\%)', 'right top'),
        }

        sample_energy_allowance_used = 23.2076127193
        sample_sent_per_node_per_sec = 4.28833268899

        custom_yaxis_range_max = {
            # Calculated so that the scale matches the energy allowance used scale exactly using two reference values
            'norm(norm(sent,time taken),num_nodes)': sample_sent_per_node_per_sec / (sample_energy_allowance_used / 100),

            'energy allowance used': 100,
        }

        results_to_load = [param for sublist in graph_parameters.keys() for param in sublist]

        protectionless_results = results.Results(
            protectionless.result_file_path,
            parameters=tuple(),
            results=results_to_load,
            network_size_normalisation="UseNumNodes"
        )

        adaptive_results = results.Results(
            adaptive.result_file_path,
            parameters=('approach',),
            results=results_to_load,
            network_size_normalisation="UseNumNodes"
        )

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=results_to_load,
            network_size_normalisation="UseNumNodes"
        )

        def graph_dual_min_max_versus(result_name1, result_name2, xaxis):
            name = 'dual-min-max-{}-versus-{}_{}-{}'.format(adaptive.name, result_name1, result_name2, xaxis)

            g = dual_min_max_versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis=xaxis, yaxis1=result_name1, yaxis2=result_name2, vary='walk length', yextractor=scalar_extractor)

            g.xaxis_label = xaxis.title()
            g.yaxis1_label = graph_parameters[(result_name1, result_name2)][0]
            g.yaxis2_label = graph_parameters[(result_name1, result_name2)][1]
            g.key_position = graph_parameters[(result_name1, result_name2)][2]

            g.yaxis_font = g.xaxis_font = "',15'"

            g.nokey = True

            g.generate_legend_graph = True

            g.point_size = 1.3
            g.line_width = 4
            g.yaxis_font = "',14'"
            g.xaxis_font = "',12'"

            g.min_label = 'Dynamic - Lowest'
            g.max_label = 'Dynamic - Highest'
            g.comparison_label = 'Phantom'
            g.baseline_label = 'Protectionless - Baseline'
            g.vary_label = ''

            g.only_show_yaxis1 = True

            if result_name1 in custom_yaxis_range_max:
                g.yaxis1_range_max = custom_yaxis_range_max[result_name1]

            if result_name2 in custom_yaxis_range_max:
                g.yaxis2_range_max = custom_yaxis_range_max[result_name2]

            g.vvalue_label_converter = lambda value: "W_h = {}".format(value)

            g.create(adaptive_results, phantom_results, baseline_results=protectionless_results)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_")
            ).run()

        for (result_name1, result_name2) in graph_parameters.keys():
            graph_dual_min_max_versus(result_name1, result_name2, 'network size')

    def run(self, args):
        super(CLI, self).run(args)

        if 'table' in args:
            self._run_table(args)

        if 'graph' in args:
            self._run_graph(args)

        if 'min-max-versus' in args:
            self._run_min_max_versus(args)

        if 'dual-min-max-versus' in args:
            self._run_dual_min_max_versus(args)
