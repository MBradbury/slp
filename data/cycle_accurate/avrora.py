from __future__ import print_function

def name():
    return __name__

def platform():
    """The hardware platform of the testbed"""
    return "micaz"

def log_mode():
    # Avrora has a special log mode that involves
    # storing the address of the buffer to be printed
    # in a variable that is watched by avrora.
    # When that variable is changed, the address of the
    # buffer it contains will be printed.
    return "avrora"

def url():
    return "about:blank"

def build_arguments():
    return {}

def fastserial_supported():
    return True

def post_build_actions(target_directory, a):
    import os.path
    import shutil

    from simulator import Configuration

    # Create main.elf
    shutil.copy(os.path.join(target_directory, "main.exe"),
                os.path.join(target_directory, "main.elf"))

    # Output topology file
    configuration = Configuration.create(a.args.configuration, a.args)

    with open(os.path.join(target_directory, "topology.txt"), "w") as topo_file:
        for (nid, (x, y)) in sorted(configuration.topology.nodes.items(), key=lambda k: k[0]):
            z = 0
            print("node{} {} {} {}".format(nid, x, y, z), file=topo_file)
