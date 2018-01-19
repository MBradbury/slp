from __future__ import print_function

from datetime import timedelta
import os
import subprocess

class Runner(object):
    required_safety_periods = True
    
    executable = 'python -OO run.py'

    def __init__(self, cluster_command, prepare_command, job_thread_count, job_repeats=1, array_job_variable=None, dry_run=False, max_walltime=None):
        self.cluster_command = cluster_command
        self.prepare_command = prepare_command
        self.job_thread_count = job_thread_count
        self.array_job_variable = array_job_variable
        self.job_repeats = job_repeats
        self.dry_run = dry_run
        self.max_walltime = max_walltime

    def add_job(self, options, name, estimated_time):
        target_directory = name[:-len(".txt")]

        if not os.path.exists(target_directory):
            raise RuntimeError("The directory for this job does not exist ({})".format(target_directory))

        word, space, options = options.partition(" ")

        module = target_directory.replace("/", ".")

        if estimated_time is None:
            estimated_time = self.max_walltime

        if estimated_time is not None and self.max_walltime is not None:
            if estimated_time > self.max_walltime:
                print(f"Warning: The estimated cluster time is {estimated_time}, overriding this with the maximum cluster time of {self.max_walltime}")
                estimated_time = self.max_walltime

        if estimated_time is None:
            estimated_time = timedelta(hours=100)

        total_seconds = int(estimated_time.total_seconds())
        hours, remainder = divmod(total_seconds, 60*60)
        minutes, seconds = divmod(remainder, 60)
        estimated_time_str = "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)

        cluster_command = self.cluster_command.format(estimated_time_str, module)

        script_command = '{} {} {} >> "{}"'.format(self.executable, module, options, name)

        # Print out any useful information that could aid in debugging
        debug_commands = [
            'date',
            'hostname',
            'pwd',
            'echo "LD_LIBRARY_PATH: $LD_LIBRARY_PATH"',
            'echo "TOSROOT: $TOSROOT"',
            'echo "PYTHONPATH: $PYTHONPATH"',
            'python --version',
            'python -c "import scipy, numpy; print(scipy.__name__, scipy.__version__); print(numpy.__name__, numpy.__version__)"',
            'lscpu'
        ]
        debug_command = " ; ".join(debug_commands)
        
        # Need to remove empty strings as bash doesn't allow `;;`
        precommand = " ; ".join(filter(None, (self.prepare_command, debug_command, script_command, 'date')))

        # If any of the options contain single quotes, then
        # they need to be escaped as the whole echo is placed within
        # single quotes
        precommand = precommand.replace("'", "'\\''")

        command = 'echo \'{}\' | {}'.format(precommand, cluster_command)

        self._submit_job(command)

    def mode(self):
        return "CLUSTER"

    def _submit_job(self, command):
        print(command)
        if not self.dry_run:
            subprocess.check_call(command, shell=True)
