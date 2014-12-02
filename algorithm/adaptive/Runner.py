import os, itertools

from data.run.common import RunSimulationsCommon

class RunSimulations(RunSimulationsCommon):
    def __init__(self, driver, results_directory, safety_periods, skip_completed_simulations=True):
        super(RunSimulations, self).__init__(driver, results_directory, skip_completed_simulations)
        self.safety_periods = safety_periods

    def run(self, exe_path, distance, sizes, source_periods, approaches, configurations, alpha, receive_ratio, repeats):
        if self.skip_completed_simulations:
            self._check_existing_results(['network_size', 'source_period', 'approach', 'configuration'])
    
        if not os.path.exists(exe_path):
            raise Exception("The file {} doesn't exist".format(exe_path))

        for (size, source_period, approach, (configuration, algorithm)) in itertools.product(sizes, source_periods, approaches, configurations):
            if not self._already_processed(repeats, size, source_period, approach, configuration):

                safety_period = 0 if self.safety_periods is None else self.safety_periods[configuration][size][source_period]

                executable = 'python {} {}'.format(
                    self.optimisations,
                    exe_path)

                options = 'algorithm.adaptive --mode {} --network-size {} --configuration {} --safety-period {} --source-period {} --approach {} --time-to-send {} --receive-ratio {} --distance {} --job-size {}'.format(
                    self.driver.mode(),
                    size,
                    configuration,
                    safety_period,

                    source_period,
                    approach,
                    
                    alpha,
                    receive_ratio,
                    distance,
                    repeats)

                filename = os.path.join(self.results_directory, '-'.join(['{}'] * 7).format(
                    size,
                    configuration,
                    source_period,
                    approach,
                    alpha,
                    receive_ratio,
                    distance).replace(".", "_") + ".txt")

                self.driver.add_job(executable, options, filename)
