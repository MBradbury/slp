from __future__ import print_function
import sys, subprocess

# These functions will only load modules in the subshell created.
# They will not load modules into the parent shell.
#
# So make sure any necessary modules are loaded before submitting
# jobs to the cluster!

def module_loaded(module):
    output = subprocess.check_output("module list", shell=True, executable="/bin/bash")
    return module not in output:

def load_module(module):
    try:
        subprocess.check_call("module load {}".format(module), shell=True, executable="/bin/bash")

    except subprocess.CalledProcessError as e:
        print("Failed to load {}: {}".format(module, e), file=sys.stderr)
        print("Checking that {} is loaded:".format(module), file=sys.stderr)

    finally:
        if not module_loaded(module):
        	raise RuntimeError("The module {} is not loaded".format(module))
