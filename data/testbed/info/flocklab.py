# Note this file was generated by ./scripts/fetch_flocklab_topology.py.
# Please make changes to that script instead of editing this file.

import numpy as np

from simulator.Topology import Topology

class FlockLab(Topology):
    """The layout of nodes on the FlockLab testbed, see: https://www.flocklab.ethz.ch/user/topology.php"""

    platform = "telosb"

    def __init__(self, subset=None):
        super(FlockLab, self).__init__()
        
        self.nodes[1] = np.array((22, 25), dtype=np.float64)
        self.nodes[2] = np.array((18, 105), dtype=np.float64)
        self.nodes[3] = np.array((90, 239), dtype=np.float64)
        self.nodes[4] = np.array((69, 65), dtype=np.float64)
        self.nodes[6] = np.array((95, 344), dtype=np.float64)
        self.nodes[7] = np.array((679, 121), dtype=np.float64)
        self.nodes[8] = np.array((80, 130), dtype=np.float64)
        self.nodes[10] = np.array((360, 200), dtype=np.float64)
        self.nodes[11] = np.array((561, 120), dtype=np.float64)
        self.nodes[13] = np.array((613, 293), dtype=np.float64)
        self.nodes[14] = np.array((628, 173), dtype=np.float64)
        self.nodes[15] = np.array((128, 121), dtype=np.float64)
        self.nodes[16] = np.array((85, 404), dtype=np.float64)
        self.nodes[17] = np.array((575, 333), dtype=np.float64)
        self.nodes[18] = np.array((233, 399), dtype=np.float64)
        self.nodes[19] = np.array((505, 345), dtype=np.float64)
        self.nodes[20] = np.array((475, 324), dtype=np.float64)
        self.nodes[22] = np.array((159, 345), dtype=np.float64)
        self.nodes[23] = np.array((300, 304), dtype=np.float64)
        self.nodes[24] = np.array((321, 393), dtype=np.float64)
        self.nodes[25] = np.array((571, 234), dtype=np.float64)
        self.nodes[26] = np.array((464, 217), dtype=np.float64)
        self.nodes[27] = np.array((270, 397), dtype=np.float64)
        self.nodes[28] = np.array((159, 304), dtype=np.float64)
        self.nodes[31] = np.array((221, 218), dtype=np.float64)
        self.nodes[32] = np.array((194, 191), dtype=np.float64)
        self.nodes[33] = np.array((71, 192), dtype=np.float64)
        #self.nodes[200] = np.array((242, 532), dtype=np.float64)
        #self.nodes[201] = np.array((157, 775), dtype=np.float64)
        #self.nodes[202] = np.array((220, 640), dtype=np.float64)
        #self.nodes[204] = np.array((144, 543), dtype=np.float64)
        
        if subset is not None:
            to_keep = {x for l in (range(start, end+1) for (start, end) in subset) for x in l}
            for key in set(self.nodes) - to_keep:
                del self.nodes[key]
        
        self._process_node_id_order("topology")

    def node_ids(self):
        """Get the node id string that identifies which nodes are being used to the testbed."""
        return " ".join(["{:03d}".format(node.nid) for node in sorted(self.nodes)])

    def __str__(self):
        return "FlockLab<>"

