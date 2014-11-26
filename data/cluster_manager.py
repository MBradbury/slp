
# These functions will only load modules in the subshell created.
# They will not load modules into the parent shell.
#
# So make sure any necessary modules are loaded before submitting
# jobs to the cluster!
"""
import sys, subprocess

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
"""

def load(args):
    import pkgutil
    import data.cluster as clusters

    cluster_modules = {modname: importer for (importer, modname, ispkg) in pkgutil.iter_modules(clusters.__path__)}
    cluster_names = list(set(args).intersection(cluster_modules.keys()))

    if len(cluster_names) != 1:
        raise RuntimeError("There is not one and only one cluster name specified ({})".format(cluster_names))

    cluster_name = cluster_names[0]

    return cluster_modules[cluster_name].find_module(cluster_name).load_module(cluster_name)
