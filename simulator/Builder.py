import subprocess
import sys

ALLOWED_PLATFORMS = ("micaz", "telosb")

def build_sim(directory, **kwargs):

    flags = " ".join("-D{}={}".format(k, repr(v)) for (k, v) in kwargs.items())

    command = 'make micaz sim SLP_PARAMETER_CFLAGS="{}"'.format(flags)

    result = subprocess.check_call(
        command,
        cwd=directory,
        shell=True,
        stdout=sys.stderr,
        stderr=sys.stderr
        )

    return result

def build_actual(directory, kind, **kwargs):

    if kind not in ALLOWED_PLATFORMS:
        raise RuntimeError("Unknown build platform {}. Only {} are allowed.".format(kind, ALLOWED_PLATFORMS))

    flags = " ".join("-D{}={}".format(k, repr(v)) for (k, v) in kwargs.items())

    command = 'make {} SLP_PARAMETER_CFLAGS="{}" USE_SERIAL_PRINTF=1'.format(kind, flags)

    result = subprocess.check_call(
        command,
        cwd=directory,
        shell=True,
        stdout=sys.stderr,
        stderr=sys.stderr
        )

    return result
