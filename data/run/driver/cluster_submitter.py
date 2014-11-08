import os
import subprocess

class Runner:
    def __init__(self):
        pass

    def add_job(self, executable, options, name):
        target_directory = name[:-len(".txt")]

        word, space, options = options.partition(" ")

        module = target_directory.replace("/", ".")

        cluster_command = "qsub -q serial -j oe -V -l nodes=1:ppn=4 -l walltime=250:00:00 -N {}".format(module)

        script_command = '{} {} {} > {}'.format(executable, module, options, name)

        command = 'echo "cd \$PBS_O_WORKDIR ; {}" | {}'.format(script_command, cluster_command)

        print(command)
        subprocess.check_call(command, shell=True)


    def wait_for_completion(self):
        pass

    def fetch_results(self):
        pass

    def mode(self):
        return "CLUSTER"
