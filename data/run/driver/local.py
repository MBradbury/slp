
import os
import subprocess

from data.progress import Progress

class Runner(object):
    required_safety_periods = True
    
    executable = 'python3 -OO -X faulthandler run.py'

    local_log = "local.log"

    def __init__(self):
        self._progress = Progress("running locally")
        self.total_job_size = None
        self._jobs_executed = 0

    def add_job(self, options, name, estimated_time):

        if not self._progress.has_started():
            self._progress.start(self.total_job_size)

        # Check for overwriting results files
        if os.path.exists(name):
            raise RuntimeError(f"Would overwriting {name}, terminating to avoid doing so.")

        print(f'{self.executable} {options} > {name} (overwriting={os.path.exists(name)})')

        with open(local_log, 'w') as log_file, \
             open(name,'w') as out_file:
            subprocess.call(f"{self.executable} {options}", stdout=out_file, stderr=log_file, shell=True)

        self._progress.print_progress(self._jobs_executed)

        self._jobs_executed += 1

    def mode(self):
        return "PARALLEL"
