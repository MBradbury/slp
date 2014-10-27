import subprocess
import os
import fnmatch
import itertools

from .common import RunSimulationsCommon

class RunSimulations(RunSimulationsCommon):
    def __init__(self, driver, results_directory, safety_periods, skip_completed_simulations=True):
        super().__init__(driver, results_directory, skip_completed_simulations)
        self.safety_periods = safety_periods

    def run(self, jar_path, sizes, source_periods, configurations, repeats):
        if self.skip_completed_simulations:
            self._check_existing_results()
    
        if not os.path.exists(jar_path):
            raise Exception("The file {} doesn't exist".format(jar_path))

        for (size, source_period, (type, configuration, algorithm)) in itertools.product(sizes, source_periods, configurations):
            if not self._already_processed(size, source_period, configuration, repeats):

                safety_period = self.safety_periods[configuration][size][source_rate]

                command = 'java {} -cp "{}" Adaptive.Main --network-size {} --safety-period {} --source-rate {} --network-layout {} --configuration {} --algorithm {} --mode PARALLEL --job-size {}'.format(
                    self.optimisations,
                    jar_path,
                    size,
                    safety_period,
                    source_rate,
                    type,
                    configuration,
                    algorithm,
                    repeats)

                filename = os.path.join(self.results_directory, '{}-{}-{}-{}-{}-{}.txt'.format(
                    size,
                    source_rate,
                    type,
                    configuration,
                    algorithm,
                    repeats))

                self.driver.add_job(command, filename)

        self.driver.wait_for_completion()

        self.driver.fetch_results()
