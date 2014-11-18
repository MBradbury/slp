import subprocess
import os
import fnmatch
import itertools

from data.run.common import RunSimulationsCommon

class RunSimulations(RunSimulationsCommon):
    def __init__(self, driver, results_directory, safety_periods, skip_completed_simulations=True):
        super(RunSimulations, self).__init__(driver, results_directory, skip_completed_simulations)
        self.safety_periods = safety_periods

    def run(self, exe_path, distance, sizes, periods, temp_fake_durations, prs_tfs, prs_pfs, configurations, repeats):
        if self.skip_completed_simulations:
            self._check_existing_results(['network_size', 'configuration', 'source_period', 'fake_period', 'temp_fake_duration', 'pr_tfs', 'pr_pfs'])
    
        if not os.path.exists(exe_path):
            raise Exception("The file {} doesn't exist".format(exe_path))

        for (size, (source_period, fake_period), tfs_duration, pr_tfs, pr_pfs, (configuration, algorithm)) in itertools.product(sizes, periods, temp_fake_durations, prs_tfs, prs_pfs, configurations):
            if not self._already_processed(repeats, size, configuration, source_period, fake_period, tfs_duration, pr_tfs, pr_pfs):

                safety_period = 0 if self.safety_periods is None else self.safety_periods[configuration][size][source_period]

                executable = 'python {} {}'.format(
                    self.optimisations,
                    exe_path)

                options = 'algorithm.template --mode {} --network-size {} --configuration {} --safety-period {} --source-period {} --fake-period {} --temp-fake-duration {} --pr-tfs {} --pr-pfs {} --distance {} --job-size {}'.format(
                    self.driver.mode(),
                    size,
                    configuration,
                    safety_period,

                    source_period,
                    fake_period,
                    tfs_duration,
                    pr_tfs,
                    pr_pfs,
                    
                    distance,
                    repeats)

                filename = os.path.join(self.results_directory, '-'.join(['{}'] * 8).format(
                    size,
                    configuration,

                    source_period,
                    fake_period,
                    tfs_duration,
                    pr_tfs,
                    pr_pfs,
                    
                    distance).replace(".", "_") + ".txt")

                self.driver.add_job(executable, options, filename)
