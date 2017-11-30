
import numpy as np

from simulator.Topology import Topology

def name():
    return __name__

def platform():
    """The hardware platform of the testbed"""
    return "telosb"

def log_mode():
    return "printf"

def submitter(*args, **kwargs):
    raise RuntimeError(f"{name()} does not support automatic submission")

def build_arguments():
    return {}

def fastserial_supported():
    return True

class DCSWarwick(Topology):
    """The layout of the nodes in DCS Warwick."""
    def __init__(self):
        super(DCSWarwick, self).__init__()

        self.platform = "telosb"

        floor_distance = 20.0

        self.nodes[1] = np.array((floor_distance * 2 + 0, 0),   dtype=np.float64),  # CS2.01
        self.nodes[2] = np.array((floor_distance * 2 + 5, 7),   dtype=np.float64),  # CS2.08 (window)
        self.nodes[3] = np.array((floor_distance * 2 + 5, 10),  dtype=np.float64),  # CS2.08 (shelf)
        self.nodes[4] = np.array((floor_distance * 2 + 5, 5),   dtype=np.float64),  # CS2.06
        #self.nodes[5] = np.array((-100, -100), dtype=np.float64),
        self.nodes[6] = np.array((floor_distance * 1 + 5, 5), dtype=np.float64),  # CS1.02 (far end)
        self.nodes[7] = np.array((floor_distance * 1 + 5, 10), dtype=np.float64),  # CS1.02 (door)
        self.nodes[8] = np.array((floor_distance * 2 + 5, 0),   dtype=np.float64),  # CS2.02
        #self.nodes[9] = np.array((-1, -1), dtype=np.float64),  # Padding Node
        #self.nodes[10] = np.array((-1, -1), dtype=np.float64),  # Padding Node

        self._process_node_id_order("topology")

    def __str__(self):
        return "DCSWarwick<>"
