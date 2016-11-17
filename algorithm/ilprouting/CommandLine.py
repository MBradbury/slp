from __future__ import print_function

import itertools

from simulator.Simulation import Simulation
from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

from data import results, latex
from data.table import safety_period, direct_comparison, fake_result
from data.graph import summary, versus

class CLI(CommandLineCommon.CLI):

    local_parameter_names = ('buffer size',)

    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.result_file_path)

        subparser = self._subparsers.add_parser("table")

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods
        ))

        return argument_product

    def time_taken_to_safety_period(self, time_taken, first_normal_sent_time):
        return (time_taken - first_normal_sent_time) * 2.0


    def _run_table(self, args):
        noforward_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio'))

        result_table = fake_result.ResultTable(noforward_results)

        self._create_table(self.algorithm_module.name + "-results", result_table)

    def run(self, args):
        args = super(CLI, self).run(args)

        if 'table' == args.mode:
            self._run_table(args)
