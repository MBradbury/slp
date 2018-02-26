#!/usr/bin/env python3

import ast
import argparse
import subprocess
import sys

import matplotlib.pyplot as plt
import networkx as nx

import simulator.Configuration as Configuration
from simulator.Topology import OrderedId

class NetworkPredicateChecker(object):
    def __init__(self, configuration, with_node_id=False, nodes_to_show=None):
        self.configuration = configuration
        self.with_node_id = with_node_id

        self.nodes = configuration.topology.nodes

        if nodes_to_show is not None:
            self.nodes_to_show = {OrderedId(x) for l in (list(range(a, b+1)) for a, b in nodes_to_show) for x in l}

            self.nodes = {nid: coord for (nid, coord) in self.nodes.items() if nid in self.nodes_to_show}
        else:
            self.nodes_to_show = set(self.nodes.keys())

        print("Nodes:", self.nodes)

        self.graph = nx.DiGraph()
        self.graph.add_nodes_from([node.nid for node in self.nodes.keys()])

        # Store the coordinates
        for (node, coord) in self.nodes.items():
            self.graph.node[node.nid]['pos'] = coord
            self.graph.node[node.nid]['label'] = str(node)

    def draw(self, show=True):
        fig = plt.figure(figsize=(11, 8))
        ax = fig.gca()
        ax.set_axis_off()

        # Makes (0,0) be in the top left rather than the bottom left
        ax.invert_yaxis()

        # Add edges
        for node in self.nodes:

            neighbours = self.neighbour_predicate(node)

            print(node, neighbours)

            self.graph.add_edges_from((node.nid, n.nid) for n in neighbours if n in self.nodes_to_show)

            self.graph.node[node.nid]['color'] = "white" if neighbours else "#DCDCDC"
            self.graph.node[node.nid]['shape'] = 'o'
            self.graph.node[node.nid]['size'] = 550

        for src in self.configuration.source_ids:
            self.graph.node[src.nid]['shape'] = 'p'
            self.graph.node[src.nid]['size'] = 900

        for sink_id in self.configuration.sink_ids:
            self.graph.node[sink_id.nid]['shape'] = 'H'
            self.graph.node[sink_id.nid]['size'] = 900

        node_shapes = {node_data['shape'] for (node, node_data) in self.graph.nodes(data=True)}
        
        pos = nx.get_node_attributes(self.graph, 'pos')
        col = nx.get_node_attributes(self.graph, 'color')
        sizes = nx.get_node_attributes(self.graph, 'size')

        for shape in node_shapes:
            nodes = [node for (node, node_data) in self.graph.nodes(data=True) if node_data['shape'] == shape]

            color = [col[nid] for nid in nodes]
            size = [sizes[nid] for nid in nodes]

            drawn_nodes = nx.draw_networkx_nodes(self.graph, pos,
                node_shape=shape,
                node_color=color,
                node_size=size,
                nodelist=nodes,
            )

            drawn_nodes.set_edgecolor('black')

        nx.draw_networkx_edges(self.graph, pos,
            width=4,
            arrows=True
        )

        nx.draw_networkx_labels(self.graph, pos,
            labels=nx.get_node_attributes(self.graph, 'label'),
            font_size=12
        )

        file = 'pred.pdf'
        plt.savefig(file)

        subprocess.check_call(["pdfcrop", file, file])

        if show:
            plt.show()

    def evaluate_predicate(self, nid):

        dsrc = self.configuration.node_source_distance
        dsink = self._min_sink_distance

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
        dsink = self._min_sink_distance
        ssd = self._min_ssd

        return [
            neigh

            for source_id
            in self.configuration.source_ids

            for neigh
            in self.configuration.one_hop_neighbours(nid)

            #if dsrc(neigh, source_id) > dsrc(nid, source_id) and (dsink(nid) > ssd(source_id) / 2 or dsink(neigh) >= dsink(nid))

            if dsrc(neigh, source_id) > dsrc(nid, source_id) and (dsink(nid) * 2 > ssd(source_id) or dsink(neigh) >= dsink(nid))
        ]

    def _min_sink_distance(self, nid):
        dsink = self.configuration.node_sink_distance
        return min(dsink(nid, sink) for sink in self.configuration.sink_ids)

    def _min_ssd(self, source_id):
        ssd = self.configuration.ssd
        return min(ssd(sink, source_id) for sink in self.configuration.sink_ids)


def main():
    parser = argparse.ArgumentParser(description="Network Predicate Checker", add_help=True)

    parser.add_argument("-c", "--configuration", type=str, required=True, choices=Configuration.names())
    parser.add_argument("-ns", "--network-size", type=int, required=True)
    parser.add_argument("-d", "--distance", type=float, default=4.5)
    parser.add_argument("-nido", "--node-id-order", choices=("topology", "randomised"), default="topology")

    parser.add_argument("--nodes", type=ast.literal_eval, default=None, help="Show a subset of nodes")

    parser.add_argument("--with-node-id", action='store_true', default=False)
    parser.add_argument("--no-show", action='store_true', default=False)

    args = parser.parse_args(sys.argv[1:])

    configuration = Configuration.create_specific(args.configuration, args.network_size, args.distance, args.node_id_order)

    print("Creating graph for ", configuration)

    drawer = NetworkPredicateChecker(configuration, with_node_id=args.with_node_id, nodes_to_show=args.nodes)

    drawer.draw(show=not args.no_show)

if __name__ == "__main__":
    main()
