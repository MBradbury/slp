from __future__ import print_function

import os
import subprocess
import sys

ALLOWED_TOSSIM_PLATFORMS = ("micaz",)
ALLOWED_PLATFORMS = ("micaz", "telosb", "wsn430v13", "wsn430v14", "z1")
#ALLOWED_PLATFORMS = [
#    name
#    for name in os.listdir(os.path.join(os.environ["TOSDIR"], "platforms"))
#    if os.path.isdir(os.path.join(os.environ["TOSDIR"], "platforms", name))
#]

# z1 doesn't seem to support fastserial
FASTSERIAL_PLATFORMS = ("micaz", "telosb", "wsn430v13", "wsn430v14")

def make_clean(directory):
    to_remove = ("topology.txt", "app.c", "ident_flags.txt", "main.elf", "main.exe",
                 "main.ihex", "main.srec", "tos_image.xml", "wiring-check.xml", "TOSSIM.pyo")
    for file_to_remove in to_remove:
        try:
            os.remove(os.path.join(directory, file_to_remove))
        except OSError:
            pass

    return subprocess.check_call("make clean",
        cwd=directory,
        shell=True,
        stdout=sys.stderr,
        stderr=sys.stderr
        )

def build_sim(directory, platform="micaz", **kwargs):

    if platform not in ALLOWED_TOSSIM_PLATFORMS:
        raise RuntimeError(f"Unknown build platform {platform}. Only {ALLOWED_TOSSIM_PLATFORMS} are allowed.")

    max_nodes = kwargs["MAX_TOSSIM_NODES"]
    del kwargs["MAX_TOSSIM_NODES"]

    make_clean(directory)

    flags = " ".join(f"-D{k}={v!r}" for (k, v) in kwargs.items())

    make_options = {
        "SLP_PARAMETER_CFLAGS": flags,
        "MAX_TOSSIM_NODES": max_nodes,
        "PYTHON_BINARY": sys.executable
    }

    make_options_string = " ".join(f'{k}={v!r}' for (k, v) in make_options.items())

    command = f'make {platform} sim {make_options_string}'

    print(command, file=sys.stderr)

    result = subprocess.check_call(
        command,
        cwd=directory,
        shell=True,
        stdout=sys.stderr,
        stderr=sys.stderr
        )

    return result

def build_actual(directory, platform, enable_fast_serial=False, **kwargs):

    if platform not in ALLOWED_PLATFORMS:
        raise RuntimeError(f"Unknown build platform {platform}. Only {ALLOWED_PLATFORMS} are allowed.")

    del kwargs["MAX_TOSSIM_NODES"]

    make_clean(directory)

    flags = " ".join(f"-D{k}={v!r}" for (k, v) in kwargs.items())

    make_options = {
        "SLP_PARAMETER_CFLAGS": flags,
        "WSN_PLATFORM": platform
    }

    if "USE_SERIAL_PRINTF" in kwargs:
        make_options["USE_SERIAL_PRINTF"] = 1

    if "USE_SERIAL_MESSAGES" in kwargs:
        make_options["USE_SERIAL_MESSAGES"] = 1

    enable_fast_serial &= platform in FASTSERIAL_PLATFORMS

    fastserial_opt = "fastserial" if enable_fast_serial else ""

    # If this is a build for a testbed or cycle accurate simulator, make sure to pass that information
    # on to the makefile, which may need to do additional things to support that configuration.
    if "TESTBED" in kwargs:
        make_options["TESTBED"] = kwargs["TESTBED"]
    if "CYCLEACCURATE" in kwargs:
        make_options["CYCLEACCURATE"] = kwargs["CYCLEACCURATE"]

    make_options_string = " ".join(f'{k}={v!r}' for (k, v) in make_options.items())

    command = f'make {platform} {fastserial_opt} {make_options_string}'

    print(command, file=sys.stderr)

    result = subprocess.check_call(
        command,
        cwd=directory,
        shell=True,
        stdout=sys.stderr,
        stderr=sys.stderr
        )

    return result
