
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

    if not np.isscalar(data):
        (val, stddev) = data
        data = val

    if data > 0:
        return math.log10(data)
    elif data == 0:
        return 0
    else:
        return -math.log10(-data)

def scalar_extractor(x, key=None):
    if x is None:
        return None
    elif np.isscalar(x):
        return x
    else:
        if key is None:
            return x['mean']
        else:
            return x[key]['mean']

# From: https://github.com/liyanage/python-modules/blob/master/running_stats.py
# Based on http://www.johndcook.com/standard_deviation.html
class RunningStats(object):
    def __init__(self):
        self.n = 0
        self.old_m = 0
        self.new_m = 0
        self.old_s = 0
        self.new_s = 0

    def clear(self):
        self.n = 0

    def push(self, x):
        self.n += 1

        if self.n == 1:
            self.old_m = self.new_m = x
            self.old_s = 0
        else:
            self.new_m = self.old_m + (x - self.old_m) / self.n
            self.new_s = self.old_s + (x - self.old_m) * (x - self.new_m)

            self.old_m = self.new_m
            self.old_s = self.new_s

    def count(self):
        return self.n

    def mean(self):
        return self.new_m if self.n else 0.0
    
    def var(self, ddof=1):
        return self.new_s / (self.n - ddof) if self.n > 1 else 0.0
        
    def stddev(self, ddof=1):
        return math.sqrt(self.var(ddof=ddof))

    def combine(self, that):
        # See: https://math.stackexchange.com/questions/1426107/how-to-calculate-two-populations-combined-mean-and-standard-deviation
        result = RunningStats()

        result.n = self.n + that.n
        result.new_m = (self.n * self.new_m + that.n * that.new_m) / result.n

        self_sum_squares = self.new_s + self.new_m**2 * self.n
        that_sum_squares = that.new_s + that.new_m**2 * that.n

        result.new_s = (self_sum_squares + that_sum_squares) - result.new_m**2 * result.n

        return result
