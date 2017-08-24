
result_file_name = ["aggregator_log.stdout"]

def name():
    return __name__

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
