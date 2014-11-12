import subprocess

def check_module_loaded(module):
    output = subprocess.check_output("module list", shell=True, executable="/bin/bash")
    if module not in output:
        raise RuntimeError("The module {} is not loaded".format(module))

def load_module(module):
    try:
        subprocess.check_call("module load {}".format(module), shell=True, executable="/bin/bash")

    except subprocess.CalledProcessError as e:
        print("Failed to load {}: {}".format(module, e))
        print("Checking that {} is loaded:".format(module))

    finally:
        check_module_loaded(module)
