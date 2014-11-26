import os
import subprocess

class Runner:
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
            script_command, self.prepare_command, cluster_command)

        print(command)
        subprocess.check_call(command, shell=True)

    def mode(self):
        return "CLUSTER"
