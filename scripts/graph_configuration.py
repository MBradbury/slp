#!/usr/bin/env python3

import simulator.Configuration as Configuration
from simulator.ArgumentsCommon import ArgumentsCommon

import matplotlib as mpl
import matplotlib.pyplot as plt

source_colour = "#006400"
sink_colour = "#00008B"
node_colour = "#1E90FF"

def main(configuration):
    print(configuration.topology.nodes)

    items = configuration.topology.nodes.items()

    source_lxy = [(k, v[0], v[1]) for (k, v) in items if k in configuration.source_ids]
    sink_lxy = [(k, v[0], v[1]) for (k, v) in items if k in configuration.sink_ids]
    rest_lxy = [(k, v[0], v[1]) for (k, v) in items if k not in configuration.sink_ids | configuration.source_ids]

    ls, xs, ys = zip(*source_lxy)
    plt.scatter(xs, ys, label="Source", c=source_colour)

    ls, xs, ys = zip(*sink_lxy)
    plt.scatter(xs, ys, label="Sink", c=sink_colour)

    ls, xs, ys = zip(*rest_lxy)
    plt.scatter(xs, ys, label="Node", c=node_colour)

    plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=3)

    plt.show()

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Create a graph of a configuration.')
    parser.add_argument("-c", "--configuration",
                        type=str,
                        required=True)

    parser.add_argument("--seed",
                        type=int,
                        required=False,
                        help="The random seed provided to the simulator's PRNG")

    parser.add_argument("-ns", "--network-size",
                        type=ArgumentsCommon.type_positive_int,
                        required=True,
                        help="How large the network should be. Typically causes the network to contain NETWORK_SIZE^2 nodes."),

    parser.add_argument("-d", "--distance",
                        type=ArgumentsCommon.type_positive_float,
                        default=4.5,
                        help="The distance between nodes. How this is used depends on the configuration specified."),

    parser.add_argument("-nido", "--node-id-order",
                        choices=("topology", "randomised"),
                        default="topology",
                        help="With 'topology' node id orders are the same as the topology defines. 'randomised' causes the node ids to be randomised."),

    args = parser.parse_args()

    configuration = Configuration.create_specific(
        args.configuration,
        args.network_size,
        args.distance,
        args.node_id_order,
        seed=args.seed)

    main(configuration)
