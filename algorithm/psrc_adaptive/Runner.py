import os, itertools

from collections import OrderedDict

from data.run.common import RunSimulationsCommon

class RunSimulations(RunSimulationsCommon):
    def __init__(self, driver, results_directory, safety_periods, skip_completed_simulations=True):
        super(RunSimulations, self).__init__(driver, results_directory, skip_completed_simulations)
        self.safety_periods = safety_periods

    def run(self, exe_path, distance, sizes, source_periods, approaches, configurations, repeats):
        if self.skip_completed_simulations:
            self._check_existing_results(['network_size', 'source_period', 'approach', 'configuration'])
    
        if not os.path.exists(exe_path):
            raise RuntimeError("The file {} doesn't exist".format(exe_path))

        for (size, source_period, approach, (configuration, algorithm)) in itertools.product(sizes, source_periods, approaches, configurations):
            if not self._already_processed(repeats, size, source_period, approach, configuration):

                try:
                    safety_period = 0 if self.safety_periods is None else self.safety_periods[configuration][size][source_period]
                except KeyError as e:
                    raise KeyError("Failed to find the safety period key {}".format((configuration, size, source_period)), e)

                executable = 'python {} {}'.format(
                    self.optimisations,
                    exe_path)

                opts = OrderedDict()
                opts["--mode"] = self.driver.mode()
                opts["--network-size"] = size
                opts["--configuration"] = configuration
                opts["--safety-period"] = safety_period
                opts["--source-period"] = source_period
                opts["--approach"] = approach
                opts["--distance"] = distance
                opts["--job-size"] = repeats

                optItems = ["{} {}".format(k, v) for (k,v) in opts.items()]

                options = 'algorithm.psrc_adaptive ' + " ".join(optItems)

                filenameItems = (
                    size,
                    configuration,
                    source_period,
                    approach,
                    distance
                )

                filename = os.path.join(
                    self.results_directory,
                    '-'.join(map(self._sanitize_job_name, filenameItems)) + ".txt"
                )

                self.driver.add_job(executable, options, filename)
