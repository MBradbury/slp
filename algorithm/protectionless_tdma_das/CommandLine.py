from __future__ import print_function

import itertools

from simulator import CommandLineCommon

from data.table import safety_period

from data.run.common import RunSimulationsCommon as RunSimulations

class CLI(CommandLineCommon.CLI):

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
    tdma_num_slots = [200]
    slot_assignment_interval = [4]
    minimum_setup_periods = [0]
    pre_beacon_periods = [3]
    dissem_timeout = [5]

    repeats = 300

    local_parameter_names = ('slot period', 'dissem period', 'tdma num slots', 'slot assignment interval', 'minimum setup periods', 'pre beacon periods', "dissem timeout")


    def __init__(self):
        super(CLI, self).__init__(__package__)

    def _argument_product(self):
        argument_product = list(itertools.product(
            self.sizes, self.configurations,
            self.attacker_models, self.noise_models, self.communication_models,
            [self.distance], self.source_periods, self.slot_period, self.dissem_period,
            self.tdma_num_slots, self.slot_assignment_interval, self.minimum_setup_periods, self.dissem_timeout
        ))

        return argument_product

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        runner = RunSimulations(
            driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations
        )

        runner.run(self.repeats, self.parameter_names(), self._argument_product())

    def run(self, args):
        super(CLI, self).run(args)
