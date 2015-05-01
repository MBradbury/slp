
from __future__ import print_function

import os, sys

from algorithm.common import CommandLineCommon

import algorithm.protectionless as protectionless

# The import statement doesn't work, so we need to use __import__ instead
periodic = __import__(__package__, globals(), locals(), ['object'], -1)

from data.table import safety_period, fake_result
from data.graph import summary, heatmap, versus

from data import results, latex

from data.util import create_dirtree, recreate_dirtree, touch, scalar_extractor

import numpy

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    sizes = [ 11, 15, 21, 25 ]

    source_periods = [ 1.0, 0.5, 0.25, 0.125 ]

    periods = [ (src_period, src_period) for src_period in source_periods ]

    configurations = [
        'SourceCorner',
        'SinkCorner',
        'FurtherSinkCorner',
        #'Generic1',
        #'Generic2',
        
        #'RingTop',
        #'RingOpposite',
        #'RingMiddle',
        
        #'CircleEdges',
        #'CircleSourceCentre',
        #'CircleSinkCentre',

        'Source2Corners',
    ]

    attacker_models = ['SeqNoReactiveAttacker']

    repeats = 300

    parameter_names = ('walk length', 'walk retries')


    def __init__(self):
        super(CLI, self).__init__(__package__)


    def _execute_runner(self, driver, results_directory, skip_completed_simulations=True):
        safety_period_table_generator = safety_period.TableGenerator()
        safety_period_table_generator.analyse(protectionless.result_file_path)

        safety_periods = safety_period_table_generator.safety_periods()

        runner = periodic.Runner.RunSimulations(driver, results_directory, safety_periods, skip_completed_simulations)
        runner.run(
            self.executable_path, self.distance, self.sizes, self.periods,
            self.configurations, self.attacker_models, self.repeats
        )

    def run(self, args):

        if 'cluster' in args:
            self._run_cluster(args)

        if 'run' in args:
            self._run_run(args)

        if 'analyse' in args:
            self._run_analyse(args)
