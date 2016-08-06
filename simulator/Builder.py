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

    flags = " ".join("-D{}={}".format(k, repr(v)) for (k, v) in kwargs.items())

    make_options = {
        "SLP_PARAMETER_CFLAGS": flags
    }

    make_options_string = " ".join('{}={}'.format(k, repr(v)) for (k, v) in make_options.items())

    command = 'make {} sim {}'.format(platform, make_options_string)

    print(command)

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

    flags = " ".join("-D{}={}".format(k, repr(v)) for (k, v) in kwargs.items())

    make_options = {
        "SLP_PARAMETER_CFLAGS": flags,
        "USE_SERIAL_PRINTF": 1
    }

    # If this is a build for a testbed, make sure to pass that information
    # on to the makefile, which may need to do additional things to support that testbed.
    if "TESTBED" in kwargs:
        make_options["TESTBED"] = kwargs["TESTBED"]

    make_options_string = " ".join('{}={}'.format(k, repr(v)) for (k, v) in make_options.items())

    command = 'make {} fastserial {}'.format(platform, make_options_string)

    print(command)

    result = subprocess.check_call(
        command,
        cwd=directory,
        shell=True,
        stdout=sys.stderr,
        stderr=sys.stderr
        )

    return result
