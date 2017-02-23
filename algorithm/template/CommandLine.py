from __future__ import print_function

import datetime
import itertools
import os

from simulator import CommandLineCommon

import algorithm

protectionless = algorithm.import_algorithm("protectionless")
adaptive = algorithm.import_algorithm("adaptive")

from data import results, latex

from data.table import safety_period, fake_result, direct_comparison
from data.graph import summary, bar
from data.util import useful_log10

safety_period_equivalence = {
    "attacker model": {"SeqNoReactiveAttacker()": "SeqNosReactiveAttacker()"}
}

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.result_file_path, safety_period_equivalence=safety_period_equivalence)

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

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0

    def _time_estimater(self, args, **kwargs):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        size = args['network size']
        if size == 11:
            return datetime.timedelta(hours=8)
        elif size == 15:
            return datetime.timedelta(hours=12)
        elif size == 21:
            return datetime.timedelta(hours=22)
        elif size == 25:
            return datetime.timedelta(hours=38)
        else:
            raise RuntimeError("No time estimate for network sizes other than 11, 15, 21 or 25")


    def _run_table(self, args):
        template_results = results.Results(self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs'))

        result_table = fake_result.ResultTable(template_results)

        self._create_table(self.algorithm_module.name + "-results", result_table,
                           param_filter=lambda (fp, dur, ptfs, ppfs): ptfs not in {0.2, 0.3, 0.4})

        self._create_table(self.algorithm_module.name + "-results-low-prob", result_table,
                           param_filter=lambda (fp, dur, ptfs, ppfs): ptfs in {0.2, 0.3, 0.4})

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'fake': ('Total Fake Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'norm(sent,time taken)': ('Total Messages Sent per Second', 'left top'),
            'tfs': ('Number of TFS created', 'left top'),
            'pfs': ('Number of PFS created', 'left top'),
        }

        varying = [
            (('network size', ''), ('source period', ' seconds')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
            #'norm(sent,time taken)': 300,
            #'captured': 9,
            #'normal latency': 4000,
        }

        self._create_versus_graph(graph_parameters, varying, custom_yaxis_range_max)

    def _run_ccpe_comparison_table(self, args):
        from data.old_results import OldResults 

        results_to_compare = ('captured', 'fake', 'received ratio', 'tfs', 'pfs')

        old_results = OldResults('results/CCPE/template-results.csv',
            parameters=self.algorithm_module.local_parameter_names,
            results=results_to_compare)

        template_results = results.Results(self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=results_to_compare)

        result_table = direct_comparison.ResultTable(old_results, template_results)

        self._create_table(self.algorithm_module.name + '-ccpe-comparison', result_table)

    def _run_ccpe_comparison_graph(self, args):
        from data.old_results import OldResults 

        results_to_compare = ('captured', 'fake', 'received ratio', 'tfs', 'pfs')

        old_results = OldResults('results/CCPE/template-results.csv',
            parameters=self.algorithm_module.local_parameter_names,
            results=results_to_compare)

        template_results = results.Results(self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=results_to_compare)

        result_table = direct_comparison.ResultTable(old_results, template_results)

        def create_ccpe_comp_bar(show, pc=False):
            name = 'ccpe-comp-{}-{}'.format(show, "pcdiff" if pc else "diff")

            bar.Grapher(self.algorithm_module.graphs_path, result_table, name,
                shows=[show],
                extractor=lambda (diff, pcdiff): pcdiff if pc else diff
            ).create()

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_")
            ).run()

        for result_name in results_to_compare:
            create_ccpe_comp_bar(result_name, pc=True)
            create_ccpe_comp_bar(result_name, pc=False)

        def create_ccpe_comp_bar_pcdiff(modified=lambda x: x, name_addition=None):
            name = 'ccpe-comp-pcdiff'
            if name_addition is not None:
                name += '-{}'.format(name_addition)

            g = bar.Grapher(self.algorithm_module.graphs_path, result_table, name,
                shows=results_to_compare,
                extractor=lambda (diff, pcdiff): modified(pcdiff))

            g.yaxis_label = 'Percentage Difference'
            if name_addition is not None:
                g.yaxis_label += ' ({})'.format(name_addition)

            g.xaxis_label = 'Parameters (P_{TFS}, D_{TFS}, Pr(TFS), Pr(PFS))'

            g.create()

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_")
            ).run()

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
