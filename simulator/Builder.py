
import subprocess, sys

def build(directory, **kwargs):

    flags = " ".join("-D{}='{}'".format(k, v) for (k, v) in kwargs.items())

    command = 'make micaz sim safe SLP_PARAMETER_CFLAGS="{}"'.format(flags)

    result = subprocess.check_call(
        command,
        cwd=directory,
        shell=True,
        stdout=sys.stderr.fileno()
        )

    return result
