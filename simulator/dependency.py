import os

def check_tinyos():
    """Checks that the TinyOS env variables are set"""
    if "TOSROOT" not in os.environ:
        raise RuntimeError("Unable to find the path $TOSROOT in os.envrion.")

def check_all():
    """Checks all requirements are satisfied"""

    check_tinyos()
