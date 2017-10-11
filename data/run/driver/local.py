from __future__ import print_function

import os
import subprocess

from data.progress import Progress

class Runner(object):
    required_safety_periods = True
    
    executable = 'python -OO run.py'

    def __init__(self):
        self._progress = Progress("running locally")
        self.total_job_size = None
        self._jobs_executed = 0

    def add_job(self, options, name, estimated_time):

        if not self._progress.has_started():
            self._progress.start(self.total_job_size)

        print('{} {} > {} (overwriting={})'.format(self.executable, options, name, os.path.exists(name)))

        with open(name, 'w') as out_file:
            subprocess.call("{} {}".format(self.executable, options), stdout=out_file, shell=True)

        self._progress.print_progress(self._jobs_executed)

        self._jobs_executed += 1

    def mode(self):
        return "PARALLEL"
