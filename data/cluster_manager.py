
def load(name):
    """
    Used to load the correct cluster module, from a list of arguments which
    may have the cluster name in it.
    """
    
    import pkgutil
    import data.cluster as clusters

    cluster_modules = {modname: importer for (importer, modname, ispkg) in pkgutil.iter_modules(clusters.__path__) if modname == name}

    if name not in cluster_modules:
        raise RuntimeError("{} is not a valid name in {}".format(name, cluster_modules.keys()))

    return cluster_modules[name].find_module(name).load_module(name)
