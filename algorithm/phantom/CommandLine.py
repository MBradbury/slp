from __future__ import print_function

import os, itertools

from algorithm.common import CommandLineCommon

import algorithm.protectionless as protectionless

# The import statement doesn't work, so we need to use __import__ instead
adaptive = __import__("algorithm.adaptive", globals(), locals(), ['object'], -1)

from data import results

from data.table import safety_period, fake_result
from data.graph import summary, heatmap, versus, min_max_versus
from data.util import scalar_extractor

from data.run.common import RunSimulationsCommon as RunSimulations

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    noise_models = ["meyer-heavy", "casino-lab"]

    communication_models = ["low-asymmetry"]

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

    parameter_names = ('walk length', 'landmark node')


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
                self.sizes, self.source_periods, self.configurations,
                self.attacker_models, self.noise_models, self.communication_models, [self.distance],
                set(itertools.chain(*self.walk_hop_lengths.values())), self.landmark_nodes)
        ))

        names = ('network_size', 'source_period', 'configuration',
                 'attacker_model', 'noise_model', 'communication_model', 'distance', 'random_walk_hops', 'landmark_node')

        runner.run(self.executable_path, self.repeats, names, argument_product)


    def _run_table(self, args):
        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.parameter_names,
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

        heatmap_results = ['sent heatmap', 'received heatmap']

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.parameter_names,
            results=tuple(graph_parameters.keys() + heatmap_results)
        )    

        for name in heatmap_results:
            g = heatmap.Grapher(self.algorithm_module.graphs_path, phantom_results, name)
            g.palette = "defined(0 'white', 1 'black')"
            g.create()

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                self.algorithm_module.name + '-' + name.replace(" ", "_")
            ).run()

        parameters = [
            ('source period', ' seconds'),
            ('walk length', ' hops')
        ]

        for (parameter_name, parameter_unit) in parameters:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-{}'.format(yaxis.replace(" ", "_"), parameter_name.replace(" ", "-"))

                g = versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis='size', yaxis=yaxis, vary=parameter_name,
                    yextractor=scalar_extractor
                )

                g.xaxis_label = 'Network Size'
                g.yaxis_label = yaxis_label
                g.vary_label = parameter_name.title()
                g.vary_prefix = parameter_unit
                g.key_position = key_position

                g.create(phantom_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    self.algorithm_module.name + '-' + name
                ).run()

    def _run_min_max_versus(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'right top'),
        }

        custom_yaxis_range_max = {
            'sent': 450000,
            'captured': 20,
            'received ratio': 100,
        }

        protectionless_results = results.Results(
            protectionless.result_file_path,
            parameters=tuple(),
            results=graph_parameters.keys()
        )

        adaptive_results = results.Results(
            adaptive.result_file_path,
            parameters=('approach',),
            results=graph_parameters.keys()
        )

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.parameter_names,
            results=graph_parameters.keys()
        )

        def graph_min_max_versus(result_name):
            name = 'min-max-{}-versus-{}'.format(result_name, adaptive.name)

            g = min_max_versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='size', yaxis=result_name, vary='walk length', yextractor=scalar_extractor)

            g.xaxis_label = 'Network Size'
            g.yaxis_label = graph_parameters[result_name][0]
            g.key_position = graph_parameters[result_name][1]

            g.min_label = 'Dynamic - Lowest'
            g.max_label = 'Dynamic - Highest'
            g.comparison_label = 'Phantom'
            g.baseline_label = 'Protectionless - Baseline'
            g.vary_label = ''

            if result_name in custom_yaxis_range_max:
                g.yaxis_range_max = custom_yaxis_range_max[result_name]

            g.vvalue_label_converter = lambda name: "Walk Length {} Hops".format(name)

            g.create(adaptive_results, phantom_results, protectionless_results)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_")
            ).run()

        for result_name in graph_parameters.keys():
            graph_min_max_versus(result_name)

    def run(self, args):
        super(CLI, self).run(args)

        if 'table' in args:
            self._run_table(args)

        if 'graph' in args:
            self._run_graph(args)

        if 'min-max-versus' in args:
            self._run_min_max_versus(args)
