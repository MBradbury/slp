import subprocess

def load_module(module):
	try:
        subprocess.check_call("module load {}".format(module), shell=True)
    except subprocess.CalledProcessError as e:
        print("Failed to load {}: {}".format(module, e))
        print("Checking that {} is loaded:".format(module))

        # Could not load the module, so check that it is loaded
        output = subprocess.check_output("module list", shell=True)
        if module not in output:
            raise RuntimeError("The module {} is not loaded".format(module))
