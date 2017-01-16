#!/usr/bin/env python
from __future__ import print_function, division

import argparse
import subprocess
import sys

import matplotlib.pyplot as plt
import networkx as nx

import simulator.Configuration as Configuration

class NetworkPredicateChecker(object):
    def __init__(self, configuration, with_node_id=False):
        self.configuration = configuration
        self.with_node_id = with_node_id

        self.graph = nx.DiGraph()
        self.graph.add_nodes_from(configuration.topology.nodes)

        # Store the coordinates
        for (nid, coord) in configuration.topology.nodes.items():
            self.graph.node[nid]['pos'] = coord
            self.graph.node[nid]['label'] = str(nid)

    def draw(self, show=True):
        fig = plt.figure()
        ax = fig.gca()

        # Makes (0,0) be in the top left rather than the bottom left
        ax.invert_yaxis()

        # Add edges
        for nid in configuration.topology.nodes:

            neighbours = self.neighbour_predicate(nid)

            print(neighbours)

            self.graph.add_edges_from((nid, n) for n in neighbours)

            self.graph.node[nid]['color'] = "green" if neighbours else "red"

        pos = nx.get_node_attributes(self.graph, 'pos')

        col = nx.get_node_attributes(self.graph, 'color')
        color = [col[nid] for nid in xrange(0, max(col.keys()))]

        nx.draw(self.graph, pos,
                node_color=color,
                labels=nx.get_node_attributes(self.graph, 'label'),
                width=2, arrows=True)

        file = 'pred.pdf'
        plt.savefig(file)

        subprocess.check_call(["pdfcrop", file, file])

        if show:
            plt.show()

    def evaluate_predicate(self, nid):

        dsrc = self.configuration.node_source_distance
        dsink = self.configuration.node_sink_distance
        ssd = self.configuration.ssd

        return any(
            dsrc(neigh, source_id) > dsrc(nid, source_id) and
            dsink(neigh) >= dsink(nid)

            for neigh
            in self.configuration.one_hop_neighbours(nid)

            for source_id
            in self.configuration.source_ids
        )

    def neighbour_predicate(self, nid):
        dsrc = self.configuration.node_source_distance
        dsink = self.configuration.node_sink_distance
        ssd = self.configuration.ssd

        return [
            neigh

            for source_id
            in self.configuration.source_ids

            for neigh
            in self.configuration.one_hop_neighbours(nid)

            #if dsrc(neigh, source_id) > dsrc(nid, source_id) and (dsink(nid) > ssd(source_id) / 2 or dsink(neigh) >= dsink(nid))

            if dsrc(neigh, source_id) > dsrc(nid, source_id) and (dsink(nid) * 2 > ssd(source_id) or dsink(neigh) >= dsink(nid))
        ]


parser = argparse.ArgumentParser(description="Network Predicate Checker", add_help=True)

parser.add_argument("-c", "--configuration", type=str, required=True, choices=Configuration.names())
parser.add_argument("-ns", "--network-size", type=int, required=True)
parser.add_argument("-d", "--distance", type=float, default=4.5)
parser.add_argument("--node-id-order", choices=("topology", "randomised"), default="topology")

parser.add_argument("--with-node-id", action='store_true', default=False)
parser.add_argument("--no-show", action='store_true', default=False)

args = parser.parse_args(sys.argv[1:])

configuration = Configuration.create_specific(args.configuration, args.network_size, args.distance, args.node_id_order)

print("Creating graph for ", configuration)

drawer = NetworkPredicateChecker(configuration, with_node_id=args.with_node_id)

drawer.draw(show=not args.no_show)
