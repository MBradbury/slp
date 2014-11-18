import subprocess
import os
import itertools

from data.run.common import RunSimulationsCommon

class RunSimulations(RunSimulationsCommon):
    def __init__(self, driver, results_directory, skip_completed_simulations=True):
        super(RunSimulations, self).__init__(driver, results_directory, skip_completed_simulations)

    def run(self, exe_path, distance, sizes, source_periods, configurations, repeats):
        if self.skip_completed_simulations:
            self._check_existing_results(['network_size', 'source_period', 'configuration'])
        
        if not os.path.exists(exe_path):
            raise Exception("The file {} doesn't exist".format(exe_path))

        for (size, source_period, configuration) in itertools.product(sizes, source_periods, configurations):
            if not self._already_processed(repeats, size, source_period, configuration):

                executable = 'python {} {}'.format(
                    self.optimisations,
                    exe_path)

                options = 'algorithm.protectionless --mode {} --network-size {} --source-period {} --configuration {} --job-size {} --distance {}'.format(
                    self.driver.mode(),
                    size,
                    source_period,
                    configuration,
                    repeats,
                    distance)

                filename = os.path.join(self.results_directory, '{}-{}-{}-{}'.format(
                    size,
                    source_period,
                    configuration,
                    distance).replace(".", "_") + ".txt")

                self.driver.add_job(executable, options, filename)
