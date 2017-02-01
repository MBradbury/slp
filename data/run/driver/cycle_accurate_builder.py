
from . import testbed_builder

class Runner(testbed_builder.Runner):
    def __init__(self, cycle_accurate, platform=None):
        super(Runner, self).__init__(cycle_accurate, platform)

    def add_job(self, options, name, estimated_time=None):
        a, module, module_path, target_directory = super(Runner, self).add_job(options, name, estimated_time)

        self.testbed.post_build_actions(target_directory, a)

        return a, module, module_path, target_directory

    def mode(self):
        return "CYCLEACCURATE"
