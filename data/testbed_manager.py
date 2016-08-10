
def load(name):
    """
    Used to load the correct testbed module, from a list of arguments which
    may have the testbed name in it.
    """
    
    import pkgutil
    import data.testbed as testbeds

    testbed_modules = {modname: importer for (importer, modname, ispkg) in pkgutil.iter_modules(testbeds.__path__)}

    if name not in testbed_modules:
        raise RuntimeError("{} is not a valid name in {}".format(name, testbed_modules.keys()))

    return testbed_modules[name].find_module(name).load_module(name)
