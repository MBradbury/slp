from __future__ import print_function, division

import itertools

from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

from data import results
from data.table import safety_period, fake_result
class CLI(CommandLineCommon.CLI):

    local_parameter_names = ('pr fake',)

    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.result_file_path)

        subparser = self._subparsers.add_parser("table")

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.source_periods
        ))

        argument_product = [
            (s, c, am, nm, cm, d, sp, parameters.pr_fake(s))
            for (s, c, am, nm, cm, d, sp)
            in argument_product
        ]

        return argument_product


    def _run_table(self, args):
        selected_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs'))

        result_table = fake_result.ResultTable(selected_results)

        self._create_table(self.algorithm_module.name + "-results", result_table)

    def run(self, args):
        args = super(CLI, self).run(args)

        if 'table' == args.mode:
            self._run_table(args)
