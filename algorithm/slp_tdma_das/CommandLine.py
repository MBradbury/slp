from __future__ import print_function

import itertools

from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

from data.table import safety_period

from data.run.common import RunSimulationsCommon as RunSimulations

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    noise_models = ["meyer-heavy", "casino-lab"]

    communication_models = ["low-asymmetry"]

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
    ]

    attacker_models = ['SeqNosReactiveAttacker()']

    slot_period = [0.1]
    dissem_period = [0.5]
    tdma_num_slots = [120]
    slot_assignment_interval = [4]

    repeats = 300

    local_parameter_names = ('slot period', 'dissem period', 'tdma num slots', 'slot assignment interval')


    def __init__(self):
        super(CLI, self).__init__(__package__)

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        runner = RunSimulations(
            driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations
        )

        argument_product = itertools.product(
            self.sizes, self.configurations,
            self.attacker_models, self.noise_models, self.communication_models,
            [self.distance], self.source_periods, self.slot_period, self.dissem_period,
            self.tdma_num_slots, self.slot_assignment_interval
        )

        runner.run(self.executable_path, self.repeats, self.parameter_names(), list(argument_product))

    def run(self, args):
        super(CLI, self).run(args)
