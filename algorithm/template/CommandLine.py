from __future__ import print_function

from datetime import timedelta
import itertools
import os.path

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
        super(CLI, self).__init__(__package__, protectionless.name, safety_period_equivalence=safety_period_equivalence)

        subparser = self._add_argument("table", self._run_table)
        subparser = self._add_argument("graph", self._run_graph)
        subparser = self._add_argument("ccpe-comparison-table", self._run_ccpe_comparison_table)
        subparser = self._add_argument("ccpe-comparison-graph", self._run_ccpe_comparison_graph)

    def _argument_product(self, extras=None):
        parameters = self.algorithm_module.Parameters

        argument_product = itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models,
            parameters.communication_models, parameters.fault_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.periods, parameters.temp_fake_durations,
            parameters.prs_tfs, parameters.prs_pfs
        )

        argument_product = [
            (size, config, attacker, nm, cm, fm, distance, nido, lnst, src_period, fake_period, fake_dur, pr_tfs, pr_pfs)
            for (size, config, attacker, nm, cm, fm, distance, nido, lnst, (src_period, fake_period), fake_dur, pr_tfs, pr_pfs)
            in argument_product
        ]

        argument_product = self.add_extra_arguments(argument_product, extras)

        return argument_product

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0

    def _cluster_time_estimator(self, args, **kwargs):
        historical_key_names = ('network size', 'source period')

        historical = {
            (11, 0.125): timedelta(seconds=6),
            (11, 0.25): timedelta(seconds=9),
            (11, 0.5): timedelta(seconds=10),
            (11, 1.0): timedelta(seconds=12),
            (11, 2.0): timedelta(seconds=12),
            (15, 0.125): timedelta(seconds=29),
            (15, 0.25): timedelta(seconds=52),
            (15, 0.5): timedelta(seconds=54),
            (15, 1.0): timedelta(seconds=49),
            (15, 2.0): timedelta(seconds=46),
            (21, 0.125): timedelta(seconds=174),
            (21, 0.25): timedelta(seconds=334),
            (21, 0.5): timedelta(seconds=440),
            (21, 1.0): timedelta(seconds=356),
            (21, 2.0): timedelta(seconds=319),
            (25, 0.125): timedelta(seconds=609),
            (25, 0.25): timedelta(seconds=1140),
            (25, 0.5): timedelta(seconds=1277),
            (25, 1.0): timedelta(seconds=1247),
            (25, 2.0): timedelta(seconds=974),
        }

        return self._cluster_time_estimator_from_historical(
            args, kwargs, historical_key_names, historical,
            allowance=0.25,
            max_time=timedelta(days=2)
        )


    def _run_table(self, args):
        template_results = results.Results(self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs'))

        result_table = fake_result.ResultTable(template_results)

        self._create_table(self.algorithm_module.name + "-results", result_table,
                           param_filter=lambda fp, dur, ptfs, ppfs: ptfs not in {0.2, 0.3, 0.4})

        self._create_table(self.algorithm_module.name + "-results-low-prob", result_table,
                           param_filter=lambda fp, dur, ptfs, ppfs: ptfs in {0.2, 0.3, 0.4})

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
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
