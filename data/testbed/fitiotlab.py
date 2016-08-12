
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
