
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

def submitter():
    raise RuntimeError("{} does not support automatic submission".format(name()))

# Resources:
# - https://indriya.comp.nus.edu.sg/motelab/html/faq.php

class Indriya(Topology):
    """The layout of nodes on the Indriya testbed, see: https://indriya.comp.nus.edu.sg/motelab/html/motes-info.php"""
    def __init__(self):
        super(Indriya, self).__init__()

        floor_distance = 20.0

        for nid in xrange(1, 139):
            self.nodes[nid] = np.array((-100, -100), dtype=np.float64)

        self._process_node_id_order("topology")

    def __str__(self):
        return "Indriya<>"
