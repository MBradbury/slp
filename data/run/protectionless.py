import subprocess
import os
import itertools

from .common import RunSimulationsCommon

class RunSimulations(RunSimulationsCommon):
    def __init__(self, driver, results_directory, skip_completed_simulations=True):
        super().__init__(driver, results_directory, skip_completed_simulations)

    def run(self, exe_path, distance, sizes, source_periods, configurations, repeats):
        if self.skip_completed_simulations:
            self._check_existing_results()
        
        if not os.path.exists(exe_path):
            raise Exception("The file {} doesn't exist".format(exe_path))

        for (size, source_period, (type, configuration)) in itertools.product(sizes, source_periods, configurations):
            if not self._already_processed(size, source_period, configuration, type, repeats):

                command = 'python {} {} protectionless --mode PARALLEL --network-size {} --source-period {} --configuration {} --job-size {} --distance {}'.format(
                    self.optimisations,
                    exe_path,
                    size,
                    source_period,
                    configuration,
                    repeats,
                    distance)

                filename = os.path.join(self.results_directory, '{}-{}-{}-{}-{}.txt'.format(
                    size,
                    source_period,
                    configuration,
                    repeats,
                    distance))

                self.driver.add_job(command, filename)

        self.driver.wait_for_completion()

        self.driver.fetch_results()
