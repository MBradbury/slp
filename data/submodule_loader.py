
import pkgutil

def load(parent, name):
    """
    Used to load the correct submodule, from a list of arguments which
    may have the name in it.
    """

    modules = {modname: importer for (importer, modname, ispkg) in pkgutil.iter_modules(parent.__path__)}

    if name not in modules:
        raise RuntimeError("{} is not a valid name in {}".format(name, modules.keys()))

    return modules[name].find_module(name).load_module(name)
