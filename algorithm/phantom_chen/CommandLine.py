from __future__ import print_function

import os, itertools, math

import numpy as np

from algorithm.common import CommandLineCommon

import algorithm.protectionless as protectionless

from data import results

from data.table import safety_period, fake_result
from data.graph import summary, heatmap, versus, min_max_versus
from data.util import scalar_extractor

from data.run.common import RunSimulationsCommon

class RunSimulations(RunSimulationsCommon):
    def _get_safety_period(self, argument_names, arguments):
        time_taken = super(RunSimulations, self)._get_safety_period(argument_names, arguments)

        if time_taken is None:
            return None

        configuration_name = arguments[argument_names.index('configuration')]
        network_size = int(arguments[argument_names.index('network size')])
        distance = float(arguments[argument_names.index('distance')])

        configuration = Configuration.create_specific(configuration_name, network_size, distance)
        ssd = np.mean(configuration.ssd(source) for source in configuration.source_ids)

        short_walk_length = float(arguments[argument_names.index('short walk length')])
        long_walk_length = float(arguments[argument_names.index('long walk length')])

        return (1.0 + (long_walk_length / ssd)) * time_taken

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    noise_models = ["meyer-heavy"]

    communication_models = ["ideal"]

    sizes = [11, 15, 21, 25]

    source_periods = [1.0, 0.5, 0.25, 0.125]

    configurations = [
        #'SourceCorner',
        #'Source2CornerTop',
        #'Source3CornerTop',

        #'SinkCorner',
        #'SinkCorner2Source',
        #'SinkCorner3Source',

        'FurtherSinkCorner',
        'FurtherSinkCorner2Source',
        'FurtherSinkCorner3Source'

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

    attacker_models = ['SeqNosReactiveAttacker()']

    repeats = 500

    local_parameter_names = ('short walk length', 'long walk length')


    def __init__(self):
        super(CLI, self).__init__(__package__)

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        safety_period_table_generator = safety_period.TableGenerator(protectionless.result_file_path)
        time_taken = safety_period_table_generator.time_taken()

        runner = RunSimulations(driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations, safety_periods=time_taken)

        argument_product = itertools.product(
            self.sizes, self.configurations,
            self.attacker_models, self.noise_models, self.communication_models,
            [self.distance], self.source_periods
        )

        argument_product = [
            (s, c, am, nm, cm, d, sp, swl, lwl)

            for (s, c, am, nm, cm, d, sp) in argument_product

            for (swl, lwl) in self._short_long_walk_lengths(s, c, am, nm, d, sp)
        ]        

        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        runner.run(self.executable_path, self.repeats, self.parameter_names(), argument_product)

    def _short_long_walk_lengths(self, s, c, am, nm, d, sp):
        half_ssd = int(math.floor(s/2)) + 1

        half_ssd_further = s

        ssd_further = 2*s

        #walk_short = list(range(2, half_ssd))
        #walk_long = list(range(s+2, half_ssd+s))
        
        #for the Further* topology.
        walk_short = list(range(2, half_ssd_further))
        walk_long = list(range(ssd_further+2, ssd_further+half_ssd_further))

        return list(zip(walk_short, walk_long))
        

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
            'paths reached end': 4,
        }

        heatmap_results = ['sent heatmap', 'received heatmap']

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
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

                if yaxis in custom_yaxis_range_max:
                    g.yaxis_range_max = custom_yaxis_range_max[yaxis]

                g.create(phantom_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    self.algorithm_module.name + '-' + name
                ).run()

    def run(self, args):
        super(CLI, self).run(args)

        if 'table' in args:
            self._run_table(args)

        if 'graph' in args:
            self._run_graph(args)
