from __future__ import print_function

from datetime import timedelta
import itertools
import os.path

import simulator.sim
from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")
adaptive = algorithm.import_algorithm("adaptive")

from data import results, latex, submodule_loader

from data.table import safety_period, fake_result, direct_comparison
from data.graph import summary
from data.util import useful_log10

safety_period_equivalence = {
    "attacker model": {"SeqNoReactiveAttacker()": "SeqNosReactiveAttacker()"}
}

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(protectionless.name, safety_period_equivalence=safety_period_equivalence)

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--show", action="store_true", default=False)

        subparser = self._add_argument("graph", self._run_graph)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

    def _argument_product(self, sim, extras=None):
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

    def _cluster_time_estimator(self, sim, args, **kwargs):
        historical_key_names = ('network size', 'source period')

        if sim == "tossim":
            historical = {
                (7, 0.125): timedelta(seconds=6),
                (7, 0.25): timedelta(seconds=9),
                (7, 0.5): timedelta(seconds=10),
                (7, 1.0): timedelta(seconds=12),
                (7, 2.0): timedelta(seconds=12),
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
        else:
            historical = {}

        return self._cluster_time_estimator_from_historical(
            sim, args, kwargs, historical_key_names, historical,
            allowance=0.25,
            max_time=timedelta(days=2)
        )


    def _run_table(self, args):
        template_results = results.Results(
            args.sim, self.algorithm_module.result_file_path(args.sim),
            parameters=self.algorithm_module.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs'))

        result_table = fake_result.ResultTable(template_results)

        self._create_table(self.algorithm_module.name + "-results", result_table, show=args.show,
                           param_filter=lambda fp, dur, ptfs, ppfs: ptfs not in {0.2, 0.3, 0.4})

        #self._create_table(self.algorithm_module.name + "-results-low-prob", result_table, show=args.show,
        #                   param_filter=lambda fp, dur, ptfs, ppfs: ptfs in {0.2, 0.3, 0.4})

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
