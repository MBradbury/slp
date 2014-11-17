import os
import subprocess

class Runner:
    def __init__(self):
        pass

    def add_job(self, executable, options, name):
        target_directory = name[:-len(".txt")]

        word, space, options = options.partition(" ")

        module = target_directory.replace("/", ".")

        # The -h flags causes the jobs to be submitted as held. It will need to be released before it is run.
        cluster_command = "qsub -q serial -j oe -V -h -l nodes=1:ppn=4 -l walltime=250:00:00 -N {}".format(module)

        script_command = '{} {} {} > {}'.format(executable, module, options, name)

        command = 'echo "cd \$PBS_O_WORKDIR ; {}" | {}'.format(script_command, cluster_command)

        print(command)
        subprocess.check_call(command, shell=True)

    def mode(self):
        return "CLUSTER"
