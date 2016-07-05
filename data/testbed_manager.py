
def load(args):
    """
    Used to load the correct testbed module, from a list of arguments which
    may have the testbed name in it.
    """
    
    import pkgutil
    import data.testbed as testbeds

    testbed_modules = {modname: importer for (importer, modname, ispkg) in pkgutil.iter_modules(testbeds.__path__)}
    testbed_names = list(set(args).intersection(testbed_modules.keys()))

    if len(testbed_names) != 1:
        raise RuntimeError("There is not one and only one testbed name specified ({})".format(testbed_names))

    testbed_name = testbed_names[0]

    return testbed_modules[testbed_name].find_module(testbed_name).load_module(testbed_name)
