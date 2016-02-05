from __future__ import print_function

import subprocess

class Runner(object):
    def __init__(self, cluster_command, prepare_command, job_thread_count, job_repeats=1, array_job_variable=None):
        self.cluster_command = cluster_command
        self.prepare_command = prepare_command
        self.job_thread_count = job_thread_count
        self.array_job_variable = array_job_variable
        self.job_repeats = job_repeats

    def add_job(self, executable, options, name):
        target_directory = name[:-len(".txt")]

        word, space, options = options.partition(" ")

        module = target_directory.replace("/", ".")

        cluster_command = self.cluster_command.format(module)

        script_command = '{} {} {} >> "{}"'.format(executable, module, options, name)

        # Print out any useful information that could aid in debugging
        debug_commands = [
            'date',
            'hostname',
            'pwd',
            'echo "LD_LIBRARY_PATH: $LD_LIBRARY_PATH"',
            'echo "TOSROOT: $TOSROOT"',
            'echo "PYTHONPATH: $PYTHONPATH"',
            'python --version'
        ]
        debug_command = " ; ".join(debug_commands)
        
        # Need to remove empty strings as bash doesn't allow `;;`
        precommand = " ; ".join(filter(None, (self.prepare_command, debug_command, script_command, 'date')))

        command = 'echo \'{}\' | {}'.format(precommand, cluster_command)

        self._submit_job(command)

    def mode(self):
        return "CLUSTER"

    def _submit_job(self, command):
        print(command)
        subprocess.check_call(command, shell=True)
