#!/usr/bin/env python
from __future__ import print_function

import os
import re
import requests
import sys

node_url = "https://www.flocklab.ethz.ch/user/scripts/flocklab-observer-positions.js"

output_directory = "data/testbed/info/"

bad_nodes = {15}

def main():
    r = requests.get(node_url)

    if r.status_code != 200:
        raise RuntimeError("Failed to get the flocklab positions")

    matches = re.findall(r"{.*}", r.text)

    coords = []

    for match in matches:
        match = match[1:-1] # Remove {} brackets

        details = {
            str(k.strip()): int(v.strip())
            for (k, v)
            in (x.split(":") for x in match.split(","))
        }

        coords.append(details)

    print(coords)

    pypath = os.path.join(output_directory, "flocklab.py")

    with open(pypath, "w") as out_file:
        print('# Note this file was generated by {}.'.format(sys.argv[0]), file=out_file)
        print('# Please make changes to that script instead of editing this file.', file=out_file)
        print('', file=out_file)
        print('import numpy as np', file=out_file)
        print('', file=out_file)
        print('from simulator.Topology import Topology', file=out_file)
        print('', file=out_file)
        print('class FlockLab(Topology):', file=out_file)
        print('    """The layout of nodes on the FlockLab testbed, see: https://www.flocklab.ethz.ch/user/topology.php"""', file=out_file)
        print('', file=out_file)
        print('    platform = "telosb"', file=out_file)
        print('', file=out_file)
        print('    def __init__(self, subset=None):', file=out_file)
        print('        super(FlockLab, self).__init__()', file=out_file)
        print('        ', file=out_file)

        for coord in coords:
            comment = "#" if coord["node_id"] in bad_nodes else ""

            print('        {}self.nodes[{}] = np.array(({}, {}), dtype=np.float64)'.format(
                comment, coord["node_id"], coord["x"], coord["y"]), file=out_file)

        print('        ', file=out_file)

        print('        if subset is not None:', file=out_file)
        print('            to_keep = {x for l in (range(start, end+1) for (start, end) in subset) for x in l}', file=out_file)
        print('            for key in set(self.nodes) - to_keep:', file=out_file)
        print('                del self.nodes[key]', file=out_file)

        print('        ', file=out_file)
        print('        self._process_node_id_order("topology")', file=out_file)
        print('', file=out_file)

        print('    def node_ids(self):', file=out_file)
        print('        """Get the node id string that identifies which nodes are being used to the testbed."""', file=out_file)
        print('        return " ".join(["{:03d}".format(node) for node in sorted(self.nodes)])', file=out_file)
        print('', file=out_file)

        print('    def __str__(self):', file=out_file)
        print('        return "FlockLab<>"', file=out_file)
        print('', file=out_file)


if __name__ == "__main__":
    main()