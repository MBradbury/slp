import os, subprocess

def check_java():
    """Checks if the java executable can be found"""
    output = subprocess.check_output("java -version", stderr=subprocess.STDOUT, shell=True).decode("ascii", "ignore")
    if "java version" not in output:
        raise RuntimeError("Unable to find the java executable ({})".format(output))

def check_link_layer_model():
    """Checks if the LinkLayerModel has been compiled"""
    if not os.path.exists('tinyos/support/sdk/java/net/tinyos/sim/LinkLayerModel.class'):
        raise RuntimeError("The LinkLayerModel class does not exist, please compile it first!")

def check_all():
    """Checks all requirements are satisfied"""
    checks = [
        check_java,
        check_link_layer_model
    ]

    for check in checks:
        check()
