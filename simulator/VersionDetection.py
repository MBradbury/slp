
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
        ver = subprocess.check_output("java -version 2>&1 | awk '/version/ {print $3}' | egrep -o '[^\"]*'", shell=True)
        ver = ver.decode("utf-8").strip()
    except subprocess.CalledProcessError:
        ver = "<unknown java version>"

    return ver

def slp_algorithms_version():
    try:
        ver = subprocess.check_output("git rev-parse HEAD", shell=True)
        ver = ver.decode("utf-8").strip()
    except subprocess.CalledProcessError:
        ver = "<unknown slp git rev>"

    return ver

def tinyos_version():
    try:
        ver = subprocess.check_output("git rev-parse HEAD", shell=True, cwd=os.environ["TOSROOT"])
        ver = ver.decode("utf-8").strip()
    except subprocess.CalledProcessError:
        ver = "<unknown tinyos git rev>"
    except KeyError:
        ver = "<unknown tinyos path>"

    return ver

def avrora_version():
    try:
        ver = subprocess.check_output("java -jar {} -version -colors=false".format(os.environ["AVRORA_JAR_PATH"]), shell=True)
        ver = ver.decode("utf-8").strip()
        ver = ver.split("\n")[0]
    except subprocess.CalledProcessError:
        ver = "<unknown avrora version>"
    except KeyError:
        ver = "<unknown avrora path>"

    return ver

def contiki_version():
    try:
        ver = subprocess.check_output("git describe --tags --always ; git rev-parse HEAD", shell=True, cwd=os.environ["CONTIKI_DIR"])
        ver = ver.decode("utf-8").strip().replace("\n", " ")
    except subprocess.CalledProcessError:
        ver = "<unknown contiki git rev>"
    except KeyError:
        ver = "<unknown contiki path>"

    return ver
