import os
import subprocess

class Runner:
    def __init__(self):
        pass

    def add_job(self, command, name):
        print('{} > {} (overwriting={})'.format(command, name, os.path.exists(name)))

        with open(name, 'w') as out_file:
            subprocess.call(command, stdout=out_file, shell=True)

    def wait_for_completion(self):
        pass

    def fetch_results(self):
        pass
