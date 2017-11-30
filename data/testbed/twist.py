
import numpy as np

from simulator.Topology import Topology

def name():
    return __name__

def platform():
    """The hardware platform of the testbed"""
    return ("eyesIFX", "telosa", "telosb")

def log_mode():
    return "printf"

def url():
    return "https://www.twist.tu-berlin.de"

def submitter(*args, **kwargs):
    raise RuntimeError(f"{name()} does not support automatic submission")

def build_arguments():
    return {}

def fastserial_supported():
    return True

# Resources:
# - https://www.twist.tu-berlin.de/tutorials/twist-getting-started.html#prerequisites

class Twist(Topology):
    """The layout of nodes on the TWIST testbed, see: https://www.twist.tu-berlin.de/testbeds/index.html"""
    def __init__(self):
        super(Twist, self).__init__()

        # I think there are about 279 nodes in the testbed, but that is a bit of a guess

        # Reported dead when logging into the web interface
        dead = {59, 60, 274, 275, 62, 64, 276, 277, 171, 174, 278, 279, 22, 23,
                38, 39, 40, 41, 42, 43, 44, 45, 48, 49, 52, 54, 83, 84, 172, 181,
                198, 187, 212, 203, 194, 225, 209, 207, 224, 206, 205, 211, 230,
                204, 33, 208, 222, 270, 36, 37, 220, 221, 26, 27, 189, 190}

        for nid in range(1, 280):
            # Skip any dead nodes
            if nid in dead:
                continue

            self.nodes[nid] = np.array((-100, -100), dtype=np.float64)

        self._process_node_id_order("topology")

    def __str__(self):
        return "Twist<>"
