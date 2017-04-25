from __future__ import print_function

#import os
import subprocess
import sys

ALLOWED_PLATFORMS = ("micaz", "telosb", "wsn430v13", "wsn430v14")
#ALLOWED_PLATFORMS = [
#    name
#    for name in os.listdir(os.path.join(os.environ["TOSDIR"], "platforms"))
#    if os.path.isdir(os.path.join(os.environ["TOSDIR"], "platforms", name))
#]

def build_sim(directory, platform="micaz", **kwargs):

    if platform not in ALLOWED_PLATFORMS:
        raise RuntimeError("Unknown build platform {}. Only {} are allowed.".format(platform, ALLOWED_PLATFORMS))

    max_nodes = kwargs["MAX_TOSSIM_NODES"]
    del kwargs["MAX_TOSSIM_NODES"]

    flags = " ".join("-D{}={!r}".format(k, v) for (k, v) in kwargs.items())

    make_options = {
        "SLP_PARAMETER_CFLAGS": flags,
        "MAX_TOSSIM_NODES": max_nodes
    }

    make_options_string = " ".join('{}={!r}'.format(k, v) for (k, v) in make_options.items())

    command = 'make {} sim {}'.format(platform, make_options_string)

    print(command, file=sys.stderr)

    result = subprocess.check_call(
        command,
        cwd=directory,
        shell=True,
        stdout=sys.stderr,
        stderr=sys.stderr
        )

    return result

def build_actual(directory, platform, **kwargs):

    if platform not in ALLOWED_PLATFORMS:
        raise RuntimeError("Unknown build platform {}. Only {} are allowed.".format(platform, ALLOWED_PLATFORMS))

    del kwargs["MAX_TOSSIM_NODES"]

    flags = " ".join("-D{}={!r}".format(k, v) for (k, v) in kwargs.items())

    make_options = {
        "SLP_PARAMETER_CFLAGS": flags,
        "WSN_PLATFORM": platform
    }

    if "USE_SERIAL_PRINTF" in kwargs:
        make_options["USE_SERIAL_PRINTF"] = 1

    if "USE_SERIAL_MESSAGES" in kwargs:
        make_options["USE_SERIAL_MESSAGES"] = 1

    # If this is a build for a testbed or cycle accurate simulator, make sure to pass that information
    # on to the makefile, which may need to do additional things to support that configuration.
    if "TESTBED" in kwargs:
        make_options["TESTBED"] = kwargs["TESTBED"]
    if "CYCLEACCURATE" in kwargs:
        make_options["CYCLEACCURATE"] = kwargs["CYCLEACCURATE"]

    make_options_string = " ".join('{}={!r}'.format(k, v) for (k, v) in make_options.items())

    command = 'make {} fastserial {}'.format(platform, make_options_string)

    print(command, file=sys.stderr)

    result = subprocess.check_call(
        command,
        cwd=directory,
        shell=True,
        stdout=sys.stderr,
        stderr=sys.stderr
        )

    return result
