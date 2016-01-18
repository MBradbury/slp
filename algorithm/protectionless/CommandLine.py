from __future__ import print_function

import os, itertools

from simulator.Simulator import Simulator
from algorithm.common import CommandLineCommon

from data import results, latex
from data.table import safety_period, direct_comparison
from data.graph import summary, heatmap, versus

from data.run.common import RunSimulationsCommon as RunSimulations

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    noise_models = ["casino-lab", "meyer-heavy"]

    communication_models = ["low-asymmetry"]

    sizes = [11, 15, 21, 25]

    source_periods = [1.0, 0.5, 0.25, 0.125]

    configurations = [
        #'SourceCorner',
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

        'Source2Corners',
        'Source4Corners',
        'Source2Edges',
        'Source4Edges',
        'Source2Corner',
        'SourceEdgeCorner',

        #'LineSinkCentre',
        #'SimpleTreeSinkEnd'
    ]

    repeats = 750

    attacker_models = ['SeqNoReactiveAttacker()', 'SeqNosReactiveAttacker()']

    parameter_names = tuple()

    def __init__(self):
        super(CLI, self).__init__(__package__)

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        runner = RunSimulations(driver, self.algorithm_module, result_path,
                                skip_completed_simulations=skip_completed_simulations)

        argument_product = list(itertools.product(
            self.sizes, self.source_periods, self.configurations,
            self.attacker_models, self.noise_models, self.communication_models, [self.distance]
        ))

        names = ('network_size', 'source_period', 'configuration',
                 'attacker_model', 'noise_model', 'communication_model', 'distance')

        runner.run(self.executable_path, self.repeats, names, argument_product)

    def _run_table(self, args):
        safety_period_table = safety_period.TableGenerator(self.algorithm_module.result_file_path)

        for noise_model in Simulator.available_noise_models():

            print("Writing results table for the {} noise model".format(noise_model))

            filename = '{}-{}-results'.format(self.algorithm_module.name, noise_model)

            self._create_table(filename, safety_period_table,
                               param_filter=lambda (cm, nm, am, c): nm == noise_model)

    def _run_graph(self, args):
        heatmap_parameters = ('sent heatmap', 'received heatmap')

        protectionless_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.parameter_names,
            results=heatmap_parameters
        )

        for name in heatmap_parameters:
            grapher = heatmap.Grapher(self.algorithm_module.graphs_path, protectionless_results, name)
            grapher.create()

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name.title().replace(" ", ""))
            ).run()
        
        # Don't need these as they are contained in the results file
        #for subdir in ['Collisions', 'FakeMessagesSent', 'NumPFS', 'NumTFS', 'PCCaptured', 'RcvRatio']:
        #    summary.GraphSummary(
        #        os.path.join(self.algorithm_module.graphs_path, 'Versus/{}/Source-Period'.format(subdir)),
        #        subdir).run()

    def _run_ccpe_comparison_table(self, args):
        from data.old_results import OldResults

        old_results = OldResults(
            'results/CCPE/protectionless-results.csv',
            parameters=tuple(),
            results=('time taken', 'received ratio', 'safety period')
        )

        protectionless_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.parameter_names,
            results=('time taken', 'received ratio', 'safety period')
        )

        result_table = direct_comparison.ResultTable(old_results, protectionless_results)

        self._create_table('{}-ccpe-comparison'.format(self.algorithm_module.name), result_table)

    def _run_ccpe_comparison_graphs(self, args):
        from data.old_results import OldResults

        result_names = ('time taken', 'received ratio', 'safety period')

        old_results = OldResults(
            'results/CCPE/protectionless-results.csv',
            parameters=self.parameter_names,
            results=result_names
        )

        protectionless_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.parameter_names,
            results=result_names
        )

        result_table = direct_comparison.ResultTable(old_results, protectionless_results)

        def create_ccpe_comp_versus(yxaxis, pc=False):
            name = 'ccpe-comp-{}-{}'.format(yxaxis, "pcdiff" if pc else "diff")

            versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='size', yaxis=yxaxis, vary='source period',
                yextractor=lambda (diff, pcdiff): pcdiff if pc else diff
            ).create(result_table)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_")
            ).run()

        for result_name in result_names:
            create_ccpe_comp_versus(result_name, pc=True)
            create_ccpe_comp_versus(result_name, pc=False)

    def run(self, args):
        super(CLI, self).run(args)

        if 'table' in args:
            self._run_table(args)

        if 'graph' in args:
            self._run_graph(args)

        if 'ccpe-comparison-table' in args:
            self._run_ccpe_comparison_table(args)

        if 'ccpe-comparison-graph' in args:
            self._run_ccpe_comparison_graphs(args)
