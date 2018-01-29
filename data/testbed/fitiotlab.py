
result_file_name = "aggregator_log.stdout"

generate_per_node_id_binary = True

def name():
    return __name__.split(".")[-1]

def platform():
    """The hardware platform of the testbed"""

    # 1.3b has an 868MHz radio (cc1101)
    # 1.4 has a 2.4GHz radio (cc2420)
    return ("wsn430v13", "wsn430v14")

def log_mode():
    return "unbuffered_printf"

def url():
    return "https://www.iot-lab.info"

def submitter(*args, **kwargs):
    from data.run.driver.testbed_iotlab_submitter import Runner as Submitter

    return Submitter(*args, **kwargs)

def build_arguments():
    return {
        # With IoT Lab the nodes are reset after they are all flashed to ensure
        # booting at a similar time.
        # If we do not specify this then the default of 10 minutes will be used.
        # So delay for the shortest amount of time.
        "DELAYED_BOOT_TIME_MINUTES": 1
    }

def fastserial_supported():
    return True

# Resources:
# - https://github.com/iot-lab/wsn430/tree/master/OS/TinyOS
# - https://www.iot-lab.info/hardware/wsn430/ (Difference between the two hardware types)
# - https://github.com/iot-lab/iot-lab/wiki/Hardware_Wsn430-node
# - https://www.iot-lab.info/tutorials/nodes-serial-link-aggregation/

# - https://gist.github.com/cladmi/268a84e2998d34a22b4e
# - https://lists.gforge.inria.fr/mailman/private/senslab-users/2013-March/000391.html

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

from data.testbed.info.fitiotlab.euratech import Euratech
from data.testbed.info.fitiotlab.grenoble import Grenoble
from data.testbed.info.fitiotlab.rennes import Rennes
from data.testbed.info.fitiotlab.strasbourg import Strasbourg

measurement_files = ["current.csv", "power.csv", "voltage.csv", "rssi.csv"]

def parse_measurement(result_path):

    import os.path

    import numpy as np
    import pandas

    def convert_node(node):
        # Example: wsn430-17.euratech.iot-lab.info
        return np.uint16(int(node.split(".", 1)[0].split("-", 1)[1]))

    options = {
        "current.csv": ["node", "time", "current"],
        "power.csv": ["node", "time", "power"],
        "voltage.csv": ["node", "time", "voltage"],
        "rssi.csv": ["node", "time", "rssi"],
    }

    basename = os.path.basename(result_path)

    names = options.get(basename, ["node", "time", "measurement"])

    # See: https://www.iot-lab.info/tutorials/monitor-consumption-wsn430-node/
    # Current unit is ampere
    # Voltage unit is volt
    # Power   unit is watt
    # RSSI    unit is dBm

    heading_dtypes = {
        "time": np.float_,
        "measurement": np.float_,
        "current": np.float_,
        "power": np.float_,
        "voltage": np.float_,
        "rssi": np.float_,
    }

    converters = {
        "node": convert_node
    }

    compression = None

    # Might want to try loading from compressed file instead
    result_path_gz = result_path + ".gz"
    if not os.path.exists(result_path) and os.path.exists(result_path_gz):
        result_path = result_path_gz
        compression = "gzip"

    df = pandas.read_csv(result_path,
        names=names, header=None,
        dtype=heading_dtypes, converters=converters,
        compression=compression,
    )

    return df
