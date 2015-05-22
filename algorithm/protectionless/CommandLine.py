from __future__ import print_function

import os, itertools

from algorithm.common import CommandLineCommon

from data import results, latex
from data.table import safety_period, direct_comparison
from data.graph import summary, heatmap, versus

from data.run.common import RunSimulationsCommon as RunSimulations

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    noise_model = "meyer-heavy"

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
        #'Source4Corners',
        #'Source2Edges',
        #'Source4Edges',
        #'Source2Corner',
    ]

    repeats = 750

    attacker_models = ['BasicReactiveAttacker()',
                       'IgnorePreviousLocationReactiveAttacker()',
                       'IgnorePastNLocationsReactiveAttacker(4)']

    parameter_names = tuple()

    def __init__(self):
        super(CLI, self).__init__(__package__)

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        runner = RunSimulations(driver, self.algorithm_module, result_path,
                                skip_completed_simulations=skip_completed_simulations)

        argument_product = list(itertools.product(
            self.sizes, self.source_periods, self.configurations,
            self.attacker_models, [self.noise_model], [self.distance]
        ))

        names = ('network_size', 'source_period', 'configuration',
                 'attacker_model', 'noise_model', 'distance')

        runner.run(self.executable_path, self.repeats, names, argument_product)

    def _run_table(self, args):
        safety_period_table_generator = safety_period.TableGenerator()
        safety_period_table_generator.analyse(self.algorithm_module.result_file_path)

        safety_period_table_path = '{}-results.tex'.format(self.algorithm_module.name)

        with open(safety_period_table_path, 'w') as latex_safety_period_tables:
            latex.print_header(latex_safety_period_tables)
            safety_period_table_generator.print_table(latex_safety_period_tables)
            latex.print_footer(latex_safety_period_tables)

        latex.compile_document(safety_period_table_path)

    def _run_graph(self, args):
        protectionless_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.parameter_names,
            results=('sent heatmap', 'received heatmap')
        )

        heatmap.Grapher(self.algorithm_module.graphs_path, protectionless_results, 'sent heatmap').create()
        heatmap.Grapher(self.algorithm_module.graphs_path, protectionless_results, 'received heatmap').create()

        # Don't need these as they are contained in the results file
        #for subdir in ['Collisions', 'FakeMessagesSent', 'NumPFS', 'NumTFS', 'PCCaptured', 'RcvRatio']:
        #    summary.GraphSummary(
        #        os.path.join(self.algorithm_module.graphs_path, 'Versus/{}/Source-Period'.format(subdir)),
        #        subdir).run()

        summary.GraphSummary(os.path.join(self.algorithm_module.graphs_path, 'sent heatmap'), '{}-SentHeatMap'.format(self.algorithm_module.name)).run()
        summary.GraphSummary(os.path.join(self.algorithm_module.graphs_path, 'received heatmap'), '{}-ReceivedHeatMap'.format(self.algorithm_module.name)).run()

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

        def create_comparison_table(name, param_filter=lambda x: True):
            filename = name + ".tex"

            with open(filename, 'w') as result_file:
                latex.print_header(result_file)
                result_table.write_tables(result_file, param_filter)
                latex.print_footer(result_file)

            latex.compile_document(filename)

        create_comparison_table('{}-ccpe-comparison'.format(self.algorithm_module.name))

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
