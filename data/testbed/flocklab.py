
import numpy as np

from simulator.Topology import Topology

result_file_name = "serial.csv"

def name():
    return __name__

def platform():
    """The hardware platform of the testbed"""
    # Whilst there are some tinynode motes on the testbed
    # They are practically useless as there are only 6 of them.
    return ["telosb", "tinynode"]

def log_mode():
    return "unbuffered_printf"

def url():
    return "https://www.flocklab.ethz.ch/wiki/wiki/Public/Man/Description"

def submitter(*args, **kwargs):
    from data.run.driver.testbed_flocklab_submitter import Runner as Submitter

    return Submitter(*args, **kwargs)

def build_arguments():
    return {
        # Wait for a short amount of time before running the boot event.
        # This is to help catch all the serial output
        "DELAYED_BOOT_TIME_MINUTES": 3
    }

def fastserial_supported():
    return False

# Resources:
# - https://www.flocklab.ethz.ch/wiki/wiki/Public/Index

from data.testbed.info.flocklab import FlockLab
