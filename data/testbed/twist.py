
def name():
    return __name__

def platform():
    """The hardware platform of the testbed"""
    return ("eyesIFX", "telosa", "telosb")

def log_mode():
    return "printf"

def url():
    return "https://www.twist.tu-berlin.de"

def submitter():
    raise RuntimeError("{} does not support automatic submission".format(name()))

# Resources:
# - https://www.twist.tu-berlin.de/tutorials/twist-getting-started.html#prerequisites
