
import os
import subprocess

def python_version():
    import sys
    return sys.version.replace("\n", " ")

def numpy_version():
    import numpy
    return numpy.__version__

def java_version():
    try:
        ver = subprocess.check_output("java -version 2>&1 | awk '/version/ {print $3}' | egrep -o '[^\"]*'", shell=True).strip()
    except subprocess.CalledProcessError:
        ver = "<unknown java version>"

    return ver

def slp_algorithms_version():
    try:
        ver = subprocess.check_output("hg id -n -i -b -t", shell=True).strip()
    except subprocess.CalledProcessError:
        ver = "<unknown hg rev>"

    return ver

def tinyos_version():
    try:
        ver = subprocess.check_output("git rev-parse HEAD", shell=True, cwd=os.environ["TOSROOT"]).strip()
    except subprocess.CalledProcessError:
        ver = "<unknown git rev>"
    except KeyError:
        ver = "<unknown tinyos dir>"

    return ver

def avrora_version():
    try:
        ver = subprocess.check_output("java -jar {} -version -colors=false".format(os.environ["AVRORA_JAR_PATH"]), shell=True)
        ver = ver.split("\n")[0].strip()
    except subprocess.CalledProcessError:
        ver = "<unknown avrora version>"
    except KeyError:
        ver = "<unknown avrora path>"

    return ver
