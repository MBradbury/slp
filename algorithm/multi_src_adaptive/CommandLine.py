from __future__ import print_function

import os.path, itertools

from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

from data import results

from data.table import safety_period, fake_result, comparison
from data.graph import summary, versus, bar, min_max_versus
from data.util import useful_log10, scalar_extractor

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
        'Source2Corner',
        'Source2Corners',
        'Source3Corners',
        'Source4Corners',
        'FurtherSinkSource2Corner',

        #'SourceCorner',
        #'SinkCorner',
        #'FurtherSinkCorner',
        #'Generic1',
        #'Generic2',

        #'RingTop',
        #'RingOpposite',
        #'RingMiddle',

        #'Source2Corners',
        #'Source4Corners',
        #'Source2Edges',
        #'Source4Edges',
        #'Source2Corner',
        #'SourceEdgeCorner',

        #'CircleEdges',
        #'CircleSourceCentre',
        #'CircleSinkCentre',
    ]

    attacker_models = ['SeqNosReactiveAttacker()']

    approaches = ["PB_SINK_APPROACH", "PB_ATTACKER_EST_APPROACH"]

    repeats = 500

    local_parameter_names = ('approach',)

    def __init__(self):
        super(CLI, self).__init__(__package__)


    def _argument_product(self):
        argument_product = list(itertools.product(
            self.sizes, self.configurations,
            self.attacker_models, self.noise_models, self.communication_models,
            [self.distance], self.source_periods, self.approaches
        ))

        # Factor in the number of sources when selecting the source period.
        # This is done so that regardless of the number of sources the overall
        # network's normal message generation rate is the same.
        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        safety_period_table_generator = safety_period.TableGenerator(protectionless.result_file_path)
        safety_periods = safety_period_table_generator.safety_periods()

        runner = RunSimulations(
            driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations, safety_periods=safety_periods)

        runner.run(self.executable_path, self.repeats, self.parameter_names(), self._argument_product(), self._time_estimater)


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
            'good move ratio': ('Good Move Ratio (%)', 'right top'),
            'norm(norm(sent,time taken),num_nodes)': ('Messages Sent per node per second', 'right top'),
        }

        adaptive_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation="NumSources")

        varying = [
            ("source period", " seconds"),
            ("communication model", "~")
        ]

        error_bars = set() # {'received ratio', 'good move ratio', 'norm(norm(sent,time taken),num_nodes)'}

        for (vary, vary_prefix) in varying:
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

                g.error_bars = yaxis in error_bars

                #g.nokey = True
                g.key_position = key_position

                g.create(adaptive_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    '{}-{}'.format(self.algorithm_module.name, name)
                ).run()

    def run(self, args):
        super(CLI, self).run(args)

        if 'table' in args:
            self._run_table(args)

        if 'graph' in args:
            self._run_graph(args)
