
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
    return "http://doc.ilabt.iminds.be/ilabt-documentation/wilabfacility.html"

def submitter(*args, **kwargs):
    raise RuntimeError("{} does not support automatic submission".format(name()))

def build_arguments():
    return {}

def fastserial_supported():
    return True

# Resources:
# - http://doc.ilabt.iminds.be/ilabt-documentation/wilabfacility.html

"""
class WiLabT(Topology):
    "" "The layout of nodes on the w-iLab.t testbed, see: https://indriya.comp.nus.edu.sg/motelab/html/motes-info.php" ""
    def __init__(self):
        super(WiLabT, self).__init__()

        self.platform = "telosb"

        floor_distance = 20.0

        for nid in range(1, 139):
            self.nodes[nid] = np.array((-100, -100), dtype=np.float64)

        self._process_node_id_order("topology")

    def __str__(self):
        return "WiLabT<>"
"""