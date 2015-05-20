
from __future__ import print_function

import os, sys

from algorithm.common import CommandLineCommon

import algorithm.protectionless as protectionless

# The import statement doesn't work, so we need to use __import__ instead
#import algorithm.phantom as phantom
phantom = __import__(__package__, globals(), locals(), ['object'], -1)

from data.table import safety_period, fake_result
from data.graph import summary, heatmap, versus

from data import results, latex

from data.util import create_dirtree, recreate_dirtree, touch, scalar_extractor

import numpy

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    noise_model = "casino-lab"

    sizes = [ 11, 15, 21, 25 ]

    source_periods = [ 1.0, 0.5, 0.25, 0.125 ]

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

    walk_hop_lengths = { 11: [6, 10, 14], 15: [10, 14, 18], 21: [16, 20, 24], 25: [20, 24, 28] }

    repeats = 500

    parameter_names = ('walk length',)


    def __init__(self):
        super(CLI, self).__init__(__package__)


    def _execute_runner(self, driver, results_directory, skip_completed_simulations=True):
        safety_period_table_generator = safety_period.TableGenerator()
        safety_period_table_generator.analyse(protectionless.result_file_path)

        safety_periods = safety_period_table_generator.safety_periods()

        runner = phantom.Runner.RunSimulations(driver, results_directory, safety_periods, skip_completed_simulations)
        runner.run(
            self.executable_path, self.distance, self.noise_model, self.sizes, self.source_periods, self.walk_hop_lengths,
            self.configurations, self.attacker_models, self.repeats
        )


    def _run_table(self, args):
        phantom_results = results.Results(phantom.result_file_path,
            parameters=self.parameter_names,
            results=('normal latency', 'ssd', 'captured', 'sent', 'received ratio'))

        result_table = fake_result.ResultTable(phantom_results)

        def create_phantom_table(name, param_filter=lambda x: True):
            filename = name + ".tex"

            with open(filename, 'w') as result_file:
                latex.print_header(result_file)
                result_table.write_tables(result_file, param_filter)
                latex.print_footer(result_file)

            latex.compile_document(filename)

        create_phantom_table("phantom-results")

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
        }

        heatmap_results = ['sent heatmap', 'received heatmap']

        phantom_results = results.Results(phantom.result_file_path,
            parameters=self.parameter_names,
            results=tuple(graph_parameters.keys() + heatmap_results))    

        for name in heatmap_results:
            heatmap.Grapher(phantom.graphs_path, phantom_results, name).create()
            summary.GraphSummary(os.path.join(phantom.graphs_path, name), 'phantom-' + name.replace(" ", "_")).run()

        parameters = [
            ('source period', ' seconds'),
            ('walk length', ' hops')
        ]

        for (parameter_name, parameter_unit) in parameters:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-{}'.format(yaxis.replace(" ", "_"), parameter_name.replace(" ", "-"))

                g = versus.Grapher(phantom.graphs_path, name,
                    xaxis='size', yaxis=yaxis, vary=parameter_name, yextractor=scalar_extractor)

                g.xaxis_label = 'Network Size'
                g.yaxis_label = yaxis_label
                g.vary_label = parameter_name.title()
                g.vary_prefix = parameter_unit
                g.key_position = key_position

                g.create(phantom_results)

                summary.GraphSummary(os.path.join(phantom.graphs_path, name), 'phantom-' + name).run()

    def run(self, args):
        super(CLI, self).run(args)

        if 'table' in args:
            self._run_table(args)

        if 'graph' in args:
            self._run_graph(args)
