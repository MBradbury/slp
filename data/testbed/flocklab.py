
import numpy as np

from simulator.Topology import Topology

def name():
    return __name__

def platform():
    """The hardware platform of the testbed"""
    return "telosb"

def log_mode():
    return "unbuffered_printf"

def url():
    return "https://www.flocklab.ethz.ch/wiki/wiki/Public/Man/Description"

def submitter(*args, **kwargs):
    from data.run.driver.testbed_flocklab_submitter import Runner as Submitter

    return Submitter(*args, **kwargs)

def build_arguments():
    return {}

# Resources:
# - https://www.flocklab.ethz.ch/wiki/wiki/Public/Index

class FlockLab(Topology):
    """The layout of nodes on the Flock Lab testbed, see: https://www.flocklab.ethz.ch/user/topology.php"""
    def __init__(self):
        super(FlockLab, self).__init__()

        self.platform = "telosb"

        self.nodes[1] = np.array((-100, -100), dtype=np.float64)
        self.nodes[2] = np.array((-100, -100), dtype=np.float64)
        self.nodes[4] = np.array((-100, -100), dtype=np.float64)
        self.nodes[8] = np.array((-100, -100), dtype=np.float64)
        self.nodes[15] = np.array((-100, -100), dtype=np.float64)
        self.nodes[33] = np.array((-100, -100), dtype=np.float64)
        self.nodes[3] = np.array((-100, -100), dtype=np.float64)
        self.nodes[6] = np.array((-100, -100), dtype=np.float64)
        self.nodes[16] = np.array((-100, -100), dtype=np.float64)
        self.nodes[22] = np.array((-100, -100), dtype=np.float64)
        self.nodes[28] = np.array((-100, -100), dtype=np.float64)
        self.nodes[32] = np.array((-100, -100), dtype=np.float64)
        self.nodes[31] = np.array((-100, -100), dtype=np.float64)
        self.nodes[18] = np.array((-100, -100), dtype=np.float64)
        self.nodes[27] = np.array((-100, -100), dtype=np.float64)
        self.nodes[24] = np.array((-100, -100), dtype=np.float64)
        self.nodes[23] = np.array((-100, -100), dtype=np.float64)
        self.nodes[10] = np.array((-100, -100), dtype=np.float64)
        self.nodes[26] = np.array((-100, -100), dtype=np.float64)
        self.nodes[20] = np.array((-100, -100), dtype=np.float64)
        self.nodes[19] = np.array((-100, -100), dtype=np.float64)
        self.nodes[17] = np.array((-100, -100), dtype=np.float64)
        self.nodes[13] = np.array((-100, -100), dtype=np.float64)
        self.nodes[25] = np.array((-100, -100), dtype=np.float64)
        self.nodes[14] = np.array((-100, -100), dtype=np.float64)
        self.nodes[7] = np.array((-100, -100), dtype=np.float64)
        self.nodes[11] = np.array((-100, -100), dtype=np.float64)
        self.nodes[204] = np.array((-100, -100), dtype=np.float64)
        self.nodes[200] = np.array((-100, -100), dtype=np.float64)
        self.nodes[201] = np.array((-100, -100), dtype=np.float64)
        self.nodes[202] = np.array((-100, -100), dtype=np.float64)

        self._process_node_id_order("topology")

    def __str__(self):
        return "FlockLab<>"
