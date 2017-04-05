from __future__ import print_function

import itertools

from simulator import CommandLineCommon

from data import results, latex
from data.table import safety_period, fake_result
from data.graph import summary, versus

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__)

        subparser = self._add_argument("table", self._run_table)

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models,
            parameters.communication_models, parameters.fault_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods
        ))

        return argument_product

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0


    def _run_table(self, args):
        parameters = [
            'normal latency', 'ssd', 'captured', 'sent', 'received ratio'
        ]

        self._create_results_table(parameters)
