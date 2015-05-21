import os, itertools

from collections import OrderedDict

from data.run.common import RunSimulationsCommon

class RunSimulations(RunSimulationsCommon):
    def __init__(self, driver, results_directory, safety_periods, skip_completed_simulations=True):
        super(RunSimulations, self).__init__(driver, results_directory, skip_completed_simulations)
        self.safety_periods = safety_periods

    def run(self, exe_path, distance, sizes, source_periods, approaches, configurations, attacker_models, repeats):
        if self.skip_completed_simulations:
            self._check_existing_results(['network_size', 'source_period', 'approach', 'configuration', 'attacker_model'])
    
        if not os.path.exists(exe_path):
            raise RuntimeError("The file {} doesn't exist".format(exe_path))

        argument_product = list(itertools.product(sizes, source_periods, approaches, configurations, attacker_models))

        self.driver.total_job_size = len(argument_product)

        for (size, source_period, approach, (configuration, algorithm), attacker_model) in argument_product:

            if not self._already_processed(repeats, size, source_period, approach, configuration, attacker_model):

                safety_period = self._get_safety_period(attacker_model, configuration, size, source_period)

                executable = 'python {} {}'.format(
                    self.optimisations,
                    exe_path)

                opts = OrderedDict()
                opts["--mode"] = self.driver.mode()
                opts["--network-size"] = size
                opts["--configuration"] = configuration
                opts["--attacker-model"] = attacker_model
                opts["--safety-period"] = safety_period
                opts["--source-period"] = source_period
                opts["--approach"] = approach
                opts["--distance"] = distance
                opts["--job-size"] = repeats

                opt_items = ["{} \"{}\"".format(k, v) for (k, v) in opts.items()]

                options = 'algorithm.multi_src_adaptive ' + " ".join(opt_items)

                filenameItems = (
                    size,
                    configuration,
                    attacker_model,
                    source_period,
                    approach,
                    distance
                )

                filename = os.path.join(
                    self.results_directory,
                    '-'.join(map(self._sanitize_job_name, filenameItems)) + ".txt"
                )

                self.driver.add_job(executable, options, filename)
