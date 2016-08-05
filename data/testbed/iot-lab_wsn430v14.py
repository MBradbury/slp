
def name():
    return "iot-lab"

def platform():
    """The hardware platform of the testbed"""

    # 1.3b has an 868MHz radio
    # 1.4 has a 2.4GHz radio

    return "wsn430v14"
    #return ("wsn430v13", "wsn430v14")

def url():
	return "https://www.iot-lab.info"

# Resources:
# - https://github.com/iot-lab/wsn430/tree/master/OS/TinyOS
# - https://www.iot-lab.info/hardware/wsn430/ (Difference between the two hardware types)
# - https://github.com/iot-lab/iot-lab/wiki/Hardware_Wsn430-node
