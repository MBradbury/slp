from __future__ import print_function

from simulator import CommandLineCommon

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__)
