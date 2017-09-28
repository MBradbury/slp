from __future__ import print_function

from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.name)

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0
