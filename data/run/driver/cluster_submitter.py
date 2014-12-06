import os
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

        script_command = '{} {} {} > {}'.format(executable, module, options, name)

        command = 'echo "cd \$PBS_O_WORKDIR ; {} ; {}" | {}'.format(
            self.prepare_command, script_command, cluster_command)

        self._submit_job(command)

    def mode(self):
        return "CLUSTER"

    def _submit_job(self, command):
        print(command)
        subprocess.check_call(command, shell=True)
