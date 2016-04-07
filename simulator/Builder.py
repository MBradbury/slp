
import subprocess, sys

def build_sim(directory, **kwargs):

    flags = " ".join("-D{}={}".format(k, repr(v)) for (k, v) in kwargs.items())

    command = 'make micaz sim-fast SLP_PARAMETER_CFLAGS="{}"'.format(flags)

    result = subprocess.check_call(
        command,
        cwd=directory,
        shell=True,
        stdout=sys.stderr,
        stderr=sys.stderr
        )

    return result

def build_actual(directory, **kwargs):

    flags = " ".join("-D{}={}".format(k, repr(v)) for (k, v) in kwargs.items())

    command = 'make micaz SLP_PARAMETER_CFLAGS="{}" USE_SERIAL_PRINTF=1'.format(flags)

    result = subprocess.check_call(
        command,
        cwd=directory,
        shell=True,
        stdout=sys.stderr,
        stderr=sys.stderr
        )

    return result
