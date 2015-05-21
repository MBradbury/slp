
from __future__ import print_function

import os, sys

from algorithm.common import CommandLineCommon

import algorithm.protectionless as protectionless

# The import statement doesn't work, so we need to use __import__ instead
#import algorithm.multi_src_adaptive as multi_src_adaptive
multi_src_adaptive = __import__(__package__, globals(), locals(), ['object'], -1)

from data.table import safety_period, direct_comparison
from data.graph import summary, heatmap, versus
from data import results, latex

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    sizes = [11, 15, 21, 25]

    source_periods = [1.0, 0.5, 0.25, 0.125]

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

        ('Source2Corners', 'CHOOSE'),
        ('Source4Corners', 'CHOOSE'),
        ('Source2Edges', 'CHOOSE'),
        ('Source4Edges', 'CHOOSE'),
        ('Source2Corner', 'CHOOSE')
    ]

    attacker_models = ['SeqNoReactiveAttacker']

    approaches = ['PB_AWAY_SRC_APPROACH']

    repeats = 300

    parameter_names = ('approach',)

    def __init__(self):
        super(CLI, self).__init__(__package__)


    def _execute_runner(self, driver, results_directory, skip_completed_simulations):
        safety_period_table_generator = safety_period.TableGenerator()
        safety_period_table_generator.analyse(protectionless.result_file_path)

        safety_periods = safety_period_table_generator.safety_periods()

        runner = multi_src_adaptive.Runner.RunSimulations(driver, results_directory, safety_periods, skip_completed_simulations)
        runner.run(
            self.executable_path, self.distance, self.sizes, self.source_periods,
            self.approaches, self.configurations, self.attacker_models, self.repeats
        )

    def run(self, args):
        super(CLI, self).run(args)
