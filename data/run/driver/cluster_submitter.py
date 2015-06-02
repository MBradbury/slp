from __future__ import print_function

import subprocess

class Runner(object):
    def __init__(self, cluster_command, prepare_command):
        self.cluster_command = cluster_command
        self.prepare_command = prepare_command

    def add_job(self, executable, options, name):
        target_directory = name[:-len(".txt")]

        word, space, options = options.partition(" ")

        module = target_directory.replace("/", ".")

        cluster_command = self.cluster_command.format(module)

        script_command = '{} {} {} > "{}"'.format(executable, module, options, name)

        # Print out any useful information that could aid in debugging
        debug_command = 'hostname ; pwd ; echo "LD_LIBRARY_PATH: $LD_LIBRARY_PATH" ; echo "TOSROOT: $TOSROOT" ; echo "PYTHONPATH: $PYTHONPATH"'

        command = 'echo \'cd $PBS_O_WORKDIR ; {} ; {} ; {}\' | {}'.format(
            debug_command, self.prepare_command, script_command, cluster_command)

        self._submit_job(command)

    def mode(self):
        return "CLUSTER"

    def _submit_job(self, command):
        print(command)
        subprocess.check_call(command, shell=True)
