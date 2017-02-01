from __future__ import print_function

def name():
    return __name__

def platform():
    """The hardware platform of the testbed"""
    return "micaz"

def log_mode():
    return "avrora"

def url():
    return "about:blank"

def post_build_actions(target_directory, a):
    import os.path
    import shutil

    from simulator import Configuration

    # Create main.elf
    shutil.copy(os.path.join(target_directory, "main.exe"),
                os.path.join(target_directory, "main.elf"))

    # Output topology file
    configuration = Configuration.create(a.args.configuration, a.args)

    with open(os.path.join(target_directory, "topology.txt"), "w") as tf:
        for (nid, (x, y)) in sorted(configuration.topology.nodes.items(), key=lambda k: k[0]):
            z = 0
            print("node{} {} {} {}".format(nid, x, y, z), file=tf)
