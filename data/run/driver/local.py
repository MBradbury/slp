from __future__ import print_function

import os, subprocess

class Runner:
    executable = 'python -OO run.py'

    def __init__(self):
        pass

    def add_job(self, options, name, estimated_time):
        print('{} {} > {} (overwriting={})'.format(self.executable, options, name, os.path.exists(name)))

        with open(name, 'w') as out_file:
            subprocess.call("{} {}".format(self.executable, options), stdout=out_file, shell=True)

    def mode(self):
        return "PARALLEL"
