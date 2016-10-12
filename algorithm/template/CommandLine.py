from __future__ import print_function

import itertools
import os

from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

# The import statement doesn't work, so we need to use __import__ instead
#import algorithm.template as template
template = __import__(__package__, globals(), locals(), ['object'], -1)
adaptive = __import__("algorithm.adaptive", globals(), locals(), ['object'], -1)

from data import results, latex

from data.table import safety_period, fake_result, direct_comparison
from data.graph import summary, bar
from data.util import useful_log10

import numpy

class CLI(CommandLineCommon.CLI):

    local_parameter_names = ('fake period', 'temp fake duration', 'pr(tfs)', 'pr(pfs)')

    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.result_file_path)

        subparser = self._subparsers.add_parser("table")
        subparser = self._subparsers.add_parser("graph")
        subparser = self._subparsers.add_parser("ccpe-comparison-table")
        subparser = self._subparsers.add_parser("ccpe-comparison-graph")

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.periods, parameters.temp_fake_durations,
            parameters.prs_tfs, parameters.prs_pfs
        )

        argument_product = [
            (size, config, attacker, nm, cm, distance, nido, lnst, src_period, fake_period, fake_dur, pr_tfs, pr_pfs)
            for (size, config, attacker, nm, cm, distance, nido, lnst, (src_period, fake_period), fake_dur, pr_tfs, pr_pfs)
            in argument_product
        ]

        return argument_product

    def time_taken_to_safety_period(self, time_taken, first_normal_sent_time):
        return (time_taken - first_normal_sent_time) * 2.0


    def _run_table(self, args):
        template_results = results.Results(template.result_file_path,
            parameters=self.local_parameter_names,
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
            parameters=self.local_parameter_names,
            results=versus_results)

        #for yaxis in versus_results:
        #    name = '{}-v-fake-period'.format(yaxis.replace(" ", "_"))
        #
        #    versus.Grapher(template.graphs_path, name,
        #        xaxis='network size', yaxis=yaxis, vary='fake period', yextractor=extract).create(template_results)
        #
        #    summary.GraphSummary(os.path.join(template.graphs_path, name), 'template-' + name).run()

    def _run_ccpe_comparison_table(self, args):
        from data.old_results import OldResults 

        results_to_compare = ('captured', 'fake', 'received ratio', 'tfs', 'pfs')

        old_results = OldResults('results/CCPE/template-results.csv',
            parameters=self.local_parameter_names,
            results=results_to_compare)

        template_results = results.Results(template.result_file_path,
            parameters=self.local_parameter_names,
            results=results_to_compare)

        result_table = direct_comparison.ResultTable(old_results, template_results)

        self._create_table(self.algorithm_module.name + '-ccpe-comparison', result_table)

    def _run_ccpe_comparison_graph(self, args):
        from data.old_results import OldResults 

        results_to_compare = ('captured', 'fake', 'received ratio', 'tfs', 'pfs')

        old_results = OldResults('results/CCPE/template-results.csv',
            parameters=self.local_parameter_names,
            results=results_to_compare)

        template_results = results.Results(template.result_file_path,
            parameters=self.local_parameter_names,
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
        args = super(CLI, self).run(args)

        if 'table' == args.mode:
            self._run_table(args)

        if 'graph' == args.mode:
            self._run_graph(args)

        if 'ccpe-comparison-table' == args.mode:
            self._run_ccpe_comparison_table(args)

        if 'ccpe-comparison-graph' == args.mode:
            self._run_ccpe_comparison_graph(args)
