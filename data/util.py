import os, shutil, stat, errno

def create_dirtree(path):
    if not os.path.exists(path):
        os.makedirs(path)

def recreate_dirtree(path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)

def touch(fname, times=None):
    with open(fname, 'a'):
        os.utime(fname, times)

def remove_dirtree(path):
    # From: http://trac.pythonpaste.org/pythonpaste/attachment/ticket/359/onerror.diff
    # From pathutils by Michael Foord: http://www.voidspace.org.uk/python/pathutils.html
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
        if ex.error != errno.ENOENT:
            raise
