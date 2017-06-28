
import numpy as np

from simulator.Topology import Topology

def name():
    return __name__

def platform():
    """The hardware platform of the testbed"""
    return "telosb"

def log_mode():
    return "uart_printf"

def url():
    return "https://www.flocklab.ethz.ch/wiki/wiki/Public/Man/Description"

def submitter(*args, **kwargs):
    from data.run.driver.testbed_flocklab_submitter import Runner as Submitter

    return Submitter(*args, **kwargs)

def build_arguments():
    return {}

def fastserial_supported():
	return False

# Resources:
# - https://www.flocklab.ethz.ch/wiki/wiki/Public/Index

from data.testbed.info.flocklab import FlockLab
