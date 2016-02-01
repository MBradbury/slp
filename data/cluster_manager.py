
def load(args):
    """
    Used to load the correct cluster module, from a list of arguments which
    may have the cluster name in it.
    """
    
    import pkgutil
    import data.cluster as clusters

    cluster_modules = {modname: importer for (importer, modname, ispkg) in pkgutil.iter_modules(clusters.__path__)}
    cluster_names = list(set(args).intersection(cluster_modules.keys()))

    if len(cluster_names) != 1:
        raise RuntimeError("There is not one and only one cluster name specified ({})".format(cluster_names))

    cluster_name = cluster_names[0]

    return cluster_modules[cluster_name].find_module(cluster_name).load_module(cluster_name)
