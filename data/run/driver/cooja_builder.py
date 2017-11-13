
from . import testbed_builder

class Runner(testbed_builder.Runner):
    required_safety_periods = False

    def __init__(self, cycle_accurate, max_buffer_size, platform=None):
        super(Runner, self).__init__(cycle_accurate, platform)

        self.max_buffer_size = max_buffer_size

    def add_job(self, options, name, estimated_time=None):
        a, module, module_path, target_directory = super(Runner, self).add_job(options, name, estimated_time)

        self.testbed.post_build_actions(target_directory, a)

        return a, module, module_path, target_directory

    def mode(self):
        return "CYCLEACCURATE"

    def build_arguments(self, a):
        args = super(Runner, self).build_arguments(a)

        args["COOJA_MAX_BUFFER_SIZE"] = self.max_buffer_size

        return args
