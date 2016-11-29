from __future__ import print_function

import os, itertools

from simulator import CommandLineCommon

from data import results, latex
from data.table import safety_period, direct_comparison
from data.graph import summary, versus

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__)

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods
        ))

        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product

    def run(self, args):
        args = super(CLI, self).run(args)
