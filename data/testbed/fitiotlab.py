
def name():
    return __name__

def platform():
    """The hardware platform of the testbed"""

    # 1.3b has an 868MHz radio
    # 1.4 has a 2.4GHz radio
    return ("wsn430v13", "wsn430v14")

def log_mode():
    return "unbuffered_printf"

def url():
    return "https://www.iot-lab.info"

# Resources:
# - https://github.com/iot-lab/wsn430/tree/master/OS/TinyOS
# - https://www.iot-lab.info/hardware/wsn430/ (Difference between the two hardware types)
# - https://github.com/iot-lab/iot-lab/wiki/Hardware_Wsn430-node
# - https://www.iot-lab.info/tutorials/nodes-serial-link-aggregation/

# To gather results:
# 1. Log into the correct site
#    $ ssh <login>@<site>.iot-lab.info (site = euratech, grenoble, lille, rennes, saclay, strasbourg)
# 2. Set up cli-tools
#    $ auth-cli --user <your_username>
# 3. Run serial_aggregator
#    $ serial_aggregator -i <experiment_id>
#
# After you have done #2, you could just do the following locally:
# $ ssh <login>@<site>.iot-lab.info "serial_aggregator -i <experiment_id>"

# Strasbourg - 3D grid of nodes - https://www.iot-lab.info/deployment/strasbourg/
# Rennes - Unknown - https://www.iot-lab.info/deployment/rennes/
# Saclay - Unknown - https://www.iot-lab.info/deployment/saclay/

class Grenoble(Topology):
    """The layout of nodes on the Grenbole testbed, see: https://www.iot-lab.info/testbed/maps.php?site=grenoble"""
    def __init__(self):
        super(Grenoble, self).__init__()

        floor_distance = 20.0

        for nid in xrange(1, 139):
            self.nodes[nid] = np.array((-100, -100), dtype=np.float64)

        self._process_node_id_order("topology")

    def __str__(self):
        return "Grenoble<>"

class Rennes(Topology):
    """The layout of nodes on the Rennes testbed, see: https://www.iot-lab.info/testbed/maps.php?site=rennes"""
    def __init__(self):
        super(Rennes, self).__init__()

        floor_distance = 20.0

        for nid in xrange(1, 139):
            self.nodes[nid] = np.array((-100, -100), dtype=np.float64)

        self._process_node_id_order("topology")

    def __str__(self):
        return "Rennes<>"

class Euratech(Topology):
    """The layout of nodes on the Euratech testbed, see: https://www.iot-lab.info/testbed/maps.php?site=euratech"""
    def __init__(self):
        super(Euratech, self).__init__()

        floor_distance = 20.0

        for nid in xrange(1, 139):
            self.nodes[nid] = np.array((-100, -100), dtype=np.float64)

        self._process_node_id_order("topology")

    def __str__(self):
        return "Euratech<>"

class Strasbourg(Topology):
    """The layout of nodes on the Strasbourg testbed, see: https://www.iot-lab.info/testbed/maps.php?site=strasbourg"""
    def __init__(self):
        super(Strasbourg, self).__init__()

        floor_distance = 20.0

        for nid in xrange(1, 139):
            self.nodes[nid] = np.array((-100, -100), dtype=np.float64)

        self._process_node_id_order("topology")

    def __str__(self):
        return "Strasbourg<>"

class Saclay(Topology):
    """The layout of nodes on the Saclay testbed, see: https://www.iot-lab.info/testbed/maps.php?site=saclay"""
    def __init__(self):
        super(Saclay, self).__init__()

        floor_distance = 20.0

        for nid in xrange(1, 139):
            self.nodes[nid] = np.array((-100, -100), dtype=np.float64)

        self._process_node_id_order("topology")

    def __str__(self):
        return "Saclay<>"
