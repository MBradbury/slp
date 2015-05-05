
from __future__ import print_function

import os

from algorithm.common import CommandLineCommon


import algorithm.protectionless as protectionless

# The import statement doesn't work, so we need to use __import__ instead
psrc_adaptive = __import__(__package__, globals(), locals(), ['object'], -1)

from data.table import safety_period, fake_result, comparison
from data.graph import summary, heatmap, versus, bar, min_max_versus

from data import results, latex

from data.util import useful_log10, scalar_extractor

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    sizes = [ 11, 15, 21, 25 ]

    source_periods = [ 1.0, 0.5, 0.25, 0.125 ]

    configurations = [
        ('SourceCorner', 'CHOOSE'),
        #('SinkCorner', 'CHOOSE'),
        #('FurtherSinkCorner', 'CHOOSE'),
        #('Generic1', 'CHOOSE'),
        #('Generic2', 'CHOOSE'),

        #('RingTop', 'CHOOSE'),
        #('RingOpposite', 'CHOOSE'),
        #('RingMiddle', 'CHOOSE'),

        #('CircleEdges', 'CHOOSE'),
        #('CircleSourceCentre', 'CHOOSE'),
        #('CircleSinkCentre', 'CHOOSE'),
    ]

    attacker_models = ['SeqNoReactiveAttacker']

    approaches = ["PB_SINK_APPROACH", "PB_ATTACKER_EST_APPROACH"]

    repeats = 300

    parameter_names = ('approach',)

    protectionless_configurations = [(a) for (a, build) in configurations]
    

    def __init__(self):
        super(CLI, self).__init__(__package__)


    def _execute_runner(self, driver, results_directory, skip_completed_simulations=True):
        safety_period_table_generator = safety_period.TableGenerator()
        safety_period_table_generator.analyse(protectionless.result_file_path)

        safety_periods = safety_period_table_generator.safety_periods()

        runner = psrc_adaptive.Runner.RunSimulations(driver, results_directory, safety_periods, skip_completed_simulations)
        runner.run(
            self.executable_path, self.distance, self.sizes, self.source_periods, self.approaches,
            self.configurations, self.attacker_models, self.repeats)

    def run(self, args):
        super(CLI, self).run(args)
