from __future__ import print_function

import os, itertools

from algorithm.common import CommandLineCommon

import algorithm.protectionless as protectionless

# The import statement doesn't work, so we need to use __import__ instead
#import algorithm.template as template
template = __import__(__package__, globals(), locals(), ['object'], -1)
adaptive = __import__("algorithm.adaptive", globals(), locals(), ['object'], -1)

from data import results, latex

from data.table import safety_period, fake_result, direct_comparison
from data.graph import summary, bar
from data.util import useful_log10

from data.run.common import RunSimulationsCommon as RunSimulations

import numpy

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    noise_model = "meyer-heavy"

    sizes = [11, 15, 21, 25]

    # Note that our simulation only has millisecond resolution,
    # so periods that require a resolution greater than 0.001 will be
    # truncated. An important example of this is 0.0625 which will be truncated
    # to 0.062. So 0.0625 has been rounded up.
    source_periods = [1.0, 0.5, 0.25, 0.125]
    fake_periods = [0.5, 0.25, 0.125, 0.063]

    periods = [(src, fake) for (src, fake) in itertools.product(source_periods, fake_periods) if src / 4.0 <= fake < src]

    configurations = [
        ('SourceCorner', 'CHOOSE'),
        #('SinkCorner', 'CHOOSE'),
        #('FurtherSinkCorner', 'CHOOSE'),
        #('Generic1', 'CHOOSE'),
        #('Generic2', 'CHOOSE'),

        #('RingTop', 'CHOOSE'),
        #('RingOpposite', 'CHOOSE'),
        #('RingMiddle', 'CHOOSE'),

        #('CircleEdges', 'CHOOSE'),
        #('CircleSourceCentre', 'CHOOSE'),
        #('CircleSinkCentre', 'CHOOSE'),
    ]

    attacker_models = ['SeqNoReactiveAttacker()']

    temp_fake_durations = [1, 2, 4]

    prs_tfs = [1.0, 0.9, 0.8]
    prs_pfs = [1.0]

    repeats = 500

    parameter_names = ('fake period', 'temp fake duration', 'pr(tfs)', 'pr(pfs)')

    protectionless_configurations = [name for (name, build) in configurations]
    

    def __init__(self):
        super(CLI, self).__init__(__package__)

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        safety_period_table_generator = safety_period.TableGenerator(protectionless.result_file_path)
        safety_periods = safety_period_table_generator.safety_periods()

        runner = RunSimulations(driver, self.algorithm_module, result_path,
                                skip_completed_simulations=skip_completed_simulations,
                                safety_periods=safety_periods)

        argument_product = itertools.product(
            self.sizes, self.periods, self.protectionless_configurations,
            self.attacker_models, [self.noise_model], [self.distance],
            self.temp_fake_durations, self.prs_tfs, self.prs_pfs
        )

        argument_product = [
            (size, src_period, config, attacker, noise, distance, fake_period, fake_dur, pr_tfs, pr_pfs)
            for (size, (src_period, fake_period), config, attacker, noise, distance, fake_dur, pr_tfs, pr_pfs)
            in argument_product
        ]

        names = ('network_size', 'source_period', 'configuration',
                 'attacker_model', 'noise_model', 'distance',
                 'fake_period', 'temp_fake_duration', 'pr_tfs', 'pr_pfs')

        runner.run(self.executable_path, self.repeats, names, argument_product)


    def _run_table(self, args):
        template_results = results.Results(template.result_file_path,
            parameters=self.parameter_names,
            results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs'))

        result_table = fake_result.ResultTable(template_results)

        self._create_table("template-results", result_table,
                           lambda (fp, dur, ptfs, ppfs): ptfs not in {0.2, 0.3, 0.4})

        self._create_table("template-results-low-prob", result_table,
                            lambda (fp, dur, ptfs, ppfs): ptfs in {0.2, 0.3, 0.4})

    def _run_graph(self, args):
        def extract(x):
            if numpy.isscalar(x):
                return x
            else:
                (val, stddev) = x
                return val

        versus_results = ('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs')

        template_results = results.Results(template.result_file_path,
            parameters=self.parameter_names,
            results=versus_results)

        #for yaxis in versus_results:
        #    name = '{}-v-fake-period'.format(yaxis.replace(" ", "_"))
        #
        #    versus.Grapher(template.graphs_path, name,
        #        xaxis='size', yaxis=yaxis, vary='fake period', yextractor=extract).create(template_results)
        #
        #    summary.GraphSummary(os.path.join(template.graphs_path, name), 'template-' + name).run()

    def _run_ccpe_comparison_table(self, args):
        from data.old_results import OldResults 

        results_to_compare = ('captured', 'fake', 'received ratio', 'tfs', 'pfs')

        old_results = OldResults('results/CCPE/template-results.csv',
            parameters=self.parameter_names,
            results=results_to_compare)

        template_results = results.Results(template.result_file_path,
            parameters=self.parameter_names,
            results=results_to_compare)

        result_table = direct_comparison.ResultTable(old_results, template_results)

        self._create_table(self.algorithm_module.name + '-ccpe-comparison', result_table)

    def _run_ccpe_comparison_graph(self, args):
        from data.old_results import OldResults 

        results_to_compare = ('captured', 'fake', 'received ratio', 'tfs', 'pfs')

        old_results = OldResults('results/CCPE/template-results.csv',
            parameters=self.parameter_names,
            results=results_to_compare)

        template_results = results.Results(template.result_file_path,
            parameters=self.parameter_names,
            results=results_to_compare)

        result_table = direct_comparison.ResultTable(old_results, template_results)

        def create_ccpe_comp_bar(show, pc=False):
            name = 'ccpe-comp-{}-{}'.format(show, "pcdiff" if pc else "diff")

            bar.Grapher(template.graphs_path, result_table, name,
                shows=[show],
                extractor=lambda (diff, pcdiff): pcdiff if pc else diff
            ).create()

            summary.GraphSummary(os.path.join(template.graphs_path, name), 'template-{}'.format(name).replace(" ", "_")).run()

        for result_name in results_to_compare:
            create_ccpe_comp_bar(result_name, pc=True)
            create_ccpe_comp_bar(result_name, pc=False)

        def create_ccpe_comp_bar_pcdiff(modified=lambda x: x, name_addition=None):
            name = 'ccpe-comp-pcdiff'
            if name_addition is not None:
                name += '-{}'.format(name_addition)

            g = bar.Grapher(template.graphs_path, result_table, name,
                shows=results_to_compare,
                extractor=lambda (diff, pcdiff): modified(pcdiff))

            g.yaxis_label = 'Percentage Difference'
            if name_addition is not None:
                g.yaxis_label += ' ({})'.format(name_addition)

            g.xaxis_label = 'Parameters (P_{TFS}, D_{TFS}, Pr(TFS), Pr(PFS))'

            g.create()

            summary.GraphSummary(os.path.join(template.graphs_path, name), 'template-{}'.format(name).replace(" ", "_")).run()

        create_ccpe_comp_bar_pcdiff()
        create_ccpe_comp_bar_pcdiff(useful_log10, 'log10')

    
    def run(self, args):
        super(CLI, self).run(args)

        if 'table' in args:
            self._run_table(args)

        if 'graph' in args:
            self._run_graph(args)

        if 'ccpe-comparison-table' in args:
            self._run_ccpe_comparison_table(args)

        if 'ccpe-comparison-graph' in args:
            self._run_ccpe_comparison_graph(args)
