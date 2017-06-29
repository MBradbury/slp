
import numpy as np

from simulator.Topology import Topology

def name():
    return __name__

def platform():
    """The hardware platform of the testbed"""
    return "telosb"

def log_mode():
    return "serial"

def url():
    return "https://indriya.comp.nus.edu.sg/motelab/html/index.php"

def submitter(*args, **kwargs):
    raise RuntimeError("{} does not support automatic submission".format(name()))

def build_arguments():
    return {}

def fastserial_supported():
    return True

# Resources:
# - https://indriya.comp.nus.edu.sg/motelab/html/faq.php

class Indriya(Topology):
    """The layout of nodes on the Indriya testbed, see: https://indriya.comp.nus.edu.sg/motelab/html/motes-info.php"""
    def __init__(self):
        super(Indriya, self).__init__()

        self.platform = "telosb"

        floor_distance = 20.0

        arduino_nodes = set(range(87, 113))

        for nid in range(1, 139):

            # Skip arduino nodes
            if nid in arduino_nodes:
                continue

            self.nodes[nid] = np.array((-100, -100), dtype=np.float64)

        self._process_node_id_order("topology")

    def __str__(self):
        return "Indriya<>"
