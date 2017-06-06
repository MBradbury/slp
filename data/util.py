import errno
import math
import os
import shutil
import stat

import numpy as np

def create_dirtree(path):
    if not os.path.exists(path):
        os.makedirs(path)

def recreate_dirtree(path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)

def touch(fname, times=None):
    # From: https://stackoverflow.com/questions/1158076/implement-touch-using-python
    with open(fname, 'a'):
        os.utime(fname, times)

def remove_dirtree(path):
    # From: http://trac.pythonpaste.org/pythonpaste/attachment/ticket/359/onerror.diff
    # From pathutils by Michael Foord: http://www.voidspace.org.uk/python/pathutils.html
    # See: http://stackoverflow.com/questions/2656322/python-shutil-rmtree-fails-on-windows-with-access-is-denied
    def on_rm_tree_error(func, path, exc_info):
        """
        Error handler for ``shutil.rmtree``.
        
        If the error is due to an access error (read only file)
        it attempts to add write permission and then retries.
        
        If the error is for another reason it re-raises the error.
        
        Usage : ``shutil.rmtree(path, onerror=on_rm_tree_error)``
        
        """
        if not os.access(path, os.W_OK):
            # Is the error an access error ?
            os.chmod(path, stat.S_IWUSR)
            func(path)
        else:
            raise

    if os.path.exists(path):
        shutil.rmtree(path, onerror=on_rm_tree_error)

def silent_remove(path):
    try:
        os.remove(path)
    except OSError as ex:
        # errno.ENOENT = no such file or directory
        if ex.errno != errno.ENOENT:
            raise

def useful_log10(data):
    if data is None:
        return None

    if not np.isscalar(x):
        (val, stddev) = x
        data = val

    if data > 0:
        return math.log10(data)
    elif data == 0:
        return 0
    else:
        return -math.log10(-data)

def scalar_extractor(x):
    if x is None:
        return None
    elif np.isscalar(x):
        return x
    else:
        (val, stddev) = x
        return val
