#!/usr/bin/env python3

import argparse
from collections import defaultdict
import itertools
import os.path
import pickle
import subprocess
import sys

import numpy as np
import pandas as pd

from data import submodule_loader
import data.testbed

from scripts.profile_testbed import LinkResult, CurrentDraw, RSSIResult

class ResultsProcessor(object):

    results_path = "results.pickle"
    current_path = "current.pickle"
    link_path = "link.pickle"

    def __init__(self):
        self.args = None
        self.rssi_results = None
        self.link_results = None
        self.current_results = None

    def setup(self, args):
        self.args = args

        self.testbed_topology = getattr(self._get_testbed(), args.topology)()

        with open(os.path.join(args.results_dir, self.results_path), 'rb') as pickle_file:
            self.results = pickle.load(pickle_file)

        self.rssi_results = [result for result in self.results if isinstance(result, RSSIResult)]
        self.link_results = sorted([result for result in self.results if isinstance(result, LinkResult)], key=lambda x: x.broadcasting_node_id)
        self.current_results = [result for result in self.results if isinstance(result, CurrentDraw)]

        if len(self.rssi_results) == 0:
            raise RuntimeError("No RSSI results")
        if len(self.link_results) == 0:
            raise RuntimeError("No Link results")

    def _get_testbed(self):
        return submodule_loader.load(data.testbed, self.args.testbed)

    def _combine_current_summary(self, results):
        if len(results) == 0:
            raise RuntimeError("There are no items in results")

        labels = list(self.testbed_topology.nodes.keys())

        dfs = []

        # Get each result the sum of squares
        for result in results:
            df = result.summary_df

            df["ss"] = df["var0"] * df["len"] + df["len"] * df["mean"]**2
            df["sum"] = df["mean"] * df["len"]

            df = df.set_index("node").reindex(labels, fill_value=0)[["len", "ss", "sum"]]

            dfs.append(df)

        dfs_iter = iter(dfs)
        total = next(dfs_iter)

        for df in dfs_iter:
            total = total.add(df, fill_value=0)

        total["mean"] = total["sum"] / total["len"]
        total["var"] = total["ss"] / total["len"] - total["mean"]**2
        total["std"] = np.sqrt(total["var"])

        total = total[["mean", "std", "len"]]

        return total

    def _combine_current_results(self):
        grouped_results = defaultdict(list)
        bad_nodes = defaultdict(int)
        total = None

        for result in self.current_results:
            grouped_results[result.broadcasting_node_id].append(result)

            if result.bad_df is not None:
                bad_df_as_dict = result.bad_df.to_dict(orient='index')

                for value in bad_df_as_dict.values():
                    node = int(value[('node', '')])
                    count = int(value[('current', 'len')])

                    bad_nodes[node] += count

        combined_results = {}

        for (broadcasting_node_id, results) in grouped_results.items():
            combined_result = self._combine_current_summary(results)
            
            combined_results[broadcasting_node_id] = combined_result

            if total is None:
                total = combined_result[["len"]]
            else:
                total = total.add(combined_result[["len"]], fill_value=0)

        return combined_results, total, bad_nodes

    def _get_combined_current_results(self):
        current_path = os.path.join(self.args.results_dir, self.current_path)

        if os.path.exists(current_path) and not self.args.flush:
            with open(current_path, 'rb') as pickle_file:
                return pickle.load(pickle_file)

        result = self._combine_current_results()

        with open(current_path, 'wb') as pickle_file:
            pickle.dump(result, pickle_file, protocol=pickle.HIGHEST_PROTOCOL)

        return result

    def _combine_link_results(self):
        labels = list(self.testbed_topology.nodes.keys())

        tx_powers = {result.broadcast_power for result in self.link_results}

        #print(labels)

        rssi = {power: pd.DataFrame(np.full((len(labels), len(labels)), np.nan), index=labels, columns=labels) for power in tx_powers}
        lqi = {power: pd.DataFrame(np.full((len(labels), len(labels)), np.nan), index=labels, columns=labels) for power in tx_powers}
        prr = {power: pd.DataFrame(np.full((len(labels), len(labels)), np.nan), index=labels, columns=labels) for power in tx_powers}

        # Combine results by broadcast id
        combined_results = {
            (label, power): [result for result in self.link_results if result.broadcasting_node_id == label and result.broadcast_power == power]
            for label in labels
            for power in tx_powers
        }

        for (sender, power), sender_results in combined_results.items():

            result = None

            if len(sender_results) == 1:
                result = sender_results[0]
            if len(sender_results) == 0:
                continue
            else:
                #print((sender, power), "has", len(sender_results), "results")

                sender_results_iter = iter(sender_results)

                result = next(sender_results_iter)
                for sender_result in sender_results_iter:
                    result = result.combine(sender_result)


            result_prr = result.prr()

            for other_nid in result.deliver_at_lqi:

                if sender not in labels or other_nid not in labels:
                    continue

                rssi[power].set_value(sender, other_nid, result.deliver_at_rssi[other_nid].mean())
                lqi[power].set_value(sender, other_nid, result.deliver_at_lqi[other_nid].mean())
                prr[power].set_value(sender, other_nid, result_prr[other_nid])

        return rssi, lqi, prr

    def _get_combined_link_results(self):
        link_path = os.path.join(self.args.results_dir, self.link_path)

        if os.path.exists(link_path) and not self.args.flush:
            with open(link_path, 'rb') as pickle_file:
                return pickle.load(pickle_file)

        result = self._combine_link_results()

        with open(link_path, 'wb') as pickle_file:
            pickle.dump(result, pickle_file, protocol=pickle.HIGHEST_PROTOCOL)

        return result

    def _get_link_asymmetry_results(self, result):
        new_result = {}

        for (k, df) in result.items():

            copy = df.copy()
            copy.fillna(value=np.nan, inplace=True)

            names = list(copy.columns.values)

            for (row, col) in itertools.product(names, repeat=2):
                copy[row][col] = df[row][col] - df[col][row]

            new_result[k] = copy

        return new_result

    def _get_combined_noise_floor(self):
        rssi_iter = iter(self.rssi_results)

        rssi_result = next(rssi_iter)
        for result in rssi_iter:
            rssi_result = rssi_result.combine(result)

        return rssi_result

    def print_individual_rssi(self, args):
        print("RSSI Results:")
        for result in self.rssi_results:
            for key in sorted(result.node_average.keys()):
                (nid, channel) = key
                print("Node", str(nid).rjust(4),
                      "channel", channel,
                      "rssi", "{:.2f}".format(result.node_average[key].mean()).rjust(6),
                      "+-", "{:.2f}".format(result.node_average[key].stddev())
                )

    def print_combined_rssi(self, args):
        rssi_result = self._get_combined_noise_floor()

        print("Combined RSSI Result:")
        for key in sorted(rssi_result.node_average.keys()):
            (nid, channel) = key
            print("Node", str(nid).rjust(4),
                  "channel", channel,
                  "rssi", "{:.2f}".format(rssi_result.node_average[key].mean()).rjust(6),
                  "+-", "{:.2f}".format(rssi_result.node_average[key].stddev())
            )

    def print_current_errors(self, args):
        combined_current, total_good_current, bad_current_nodes = self._get_combined_current_results()

        print("The following nodes has errors in their current measurements:")
        for (k, v) in bad_current_nodes.items():
            try:
                good_count = total_good_current.loc[k, "len"]
            except KeyError:
                good_count = 0

            print("Node {:>3} bad {:>5} badpc {:.2f}%".format(k, v, (v / (v + good_count)) * 100))

    def print_missing_results(self, args):
        tx_powers = {result.broadcast_power for result in self.link_results}

        link_bcast_nodes = {(result.broadcasting_node_id, result.broadcast_power) for result in self.link_results}
        missing_link_bcast_nodes = set(itertools.product(self.testbed_topology.nodes.keys(), tx_powers)) - link_bcast_nodes

        if len(missing_link_bcast_nodes) != 0:
            print("Missing the following link bcast results:")

            powers = {power for (node, power) in missing_link_bcast_nodes}

            split = {power: list(sorted(node for (node, p) in missing_link_bcast_nodes if p == power)) for power in powers}

            for power, nodes in split.items(): 
                print("Nodes for power {}: {}".format(power, nodes))
        else:
            print("No results are missing")

    def print_link_info(self, args):
        rssi, lqi, prr = self._get_combined_link_results()

        tx_powers = {result.broadcast_power for result in self.link_results}

        with open("link-info.txt", "w") as link_info_file:
            with pd.option_context("display.max_rows", None, "display.max_columns", None, "expand_frame_repr", False):
                for power in sorted(tx_powers):
                    print("For power level:", power, file=link_info_file)
                    print("RSSI:\n", rssi[power].round(2).replace(np.nan, ''), file=link_info_file)
                    print("LQI:\n", lqi[power].round(2).replace(np.nan, ''), file=link_info_file)
                    print("PRR:\n", prr[power].round(2).replace(np.nan, ''), file=link_info_file)
                    print("", file=link_info_file)


    def _draw_link_heatmap_fn(self, args, converter=lambda x: x, min_max=None):
        import matplotlib.pyplot as plt

        from mpl_toolkits.axes_grid1 import make_axes_locatable

        rssi, lqi, prr = map(converter, self._get_combined_link_results())

        tx_powers = {result.broadcast_power for result in self.link_results}

        details = [("prr", prr, "%"), ("rssi", rssi, "dBm"), ("lqi", lqi, "")]

        for power in sorted(tx_powers):
            for (i, (name, value, label)) in enumerate(details, start=1):

                if min_max is None:
                    vmin, vmax = None, None
                else:
                    vmin, vmax = min_max[name]

                ax = plt.subplot(1, len(details), i)
                im = ax.imshow(value[power], cmap="PiYG", aspect="equal", origin="lower", vmin=vmin, vmax=vmax)

                plt.title("{} ({})".format(name, label))
                plt.ylabel("Sender")
                plt.xlabel("Receiver")

                divider = make_axes_locatable(ax)
                cax = divider.append_axes("right", size="5%", pad=0.05)
                plt.colorbar(im, cax=cax)

                #plt.xlim(min(df.columns), max(df.columns))
                #plt.ylim(min(df.index), max(df.index))

                #plt.yticks(range(len(df.index)), df.index, size='xx-small')
                #plt.xticks(range(len(df.columns)), df.columns, size='xx-small')

            plt.subplots_adjust(wspace=0.35)

            plt.savefig("heatmap-{}.pdf".format(power))

            if args.show:
                plt.show()

    def draw_link_heatmap(self, args):
        min_max = {"prr": (0, 1), "rssi": (-100, -50), "lqi": (40, 115)}
        return self._draw_link_heatmap_fn(args, min_max=min_max)

    def draw_link_asymmetry_heatmap(self, args):
        return self._draw_link_heatmap_fn(args, self._get_link_asymmetry_results)


    def draw_link(self, args):
        import networkx as nx
        from networkx.drawing.nx_pydot import write_dot

        rssi, lqi, prr = self._get_combined_link_results()

        if args.name == "rssi":
            result = rssi
        elif args.name == "prr":
            result = prr
        elif args.name == "lqi":
            result = lqi
        else:
            raise RuntimeError("Unknown name {}".format(args.name))

        try:
            result = result[args.power]
        except KeyError:
            raise RuntimeError("No result for {} with power {}".format(args.name, args.power))

        labels = list(result.columns.values)


        G = nx.MultiDiGraph()
        G.add_nodes_from(labels)

        target_width_pixels = 1024

        xs = [coord[0] for coord in self.testbed_topology.nodes.values()]

        scale = target_width_pixels / (max(xs) - min(xs))

        for node in G:
            coords = self.testbed_topology.nodes[node]

            x, y = coords[0], coords[1]

            G.node[node]['pos'] = "{},{}".format(x * scale, y * scale)

        for node1, row in result.iterrows():
            for node2 in labels:
                if not np.isnan(row[node2]):
                    G.add_edge(node1, node2, label=round(row[node2], 2))

        dot_path = "{}-{}.dot".format(args.name, args.power)
        png_path = dot_path.replace(".dot", ".png")

        write_dot(G, dot_path)

        subprocess.check_call("neato -n2 -T png {} > {}".format(dot_path, png_path), shell=True)

        if args.show:
            subprocess.call("xdg-open {}".format(png_path), shell=True)

    def draw_noise_floor_heatmap(self, args):
        import matplotlib.pyplot as plt

        noise_floor = self._get_combined_noise_floor()

        z = {
            nid: result.mean()
            for ((nid, channel), result)
            in noise_floor.node_average.items()
            if channel == args.channel
        }

        four = [
            (nid, coords[0], coords[1], z[nid])
            for (nid, coords)
            in self.testbed_topology.nodes.items()
            if nid in z
        ]

        n, xs, ys, cs = zip(*four)

        ax = plt.gca()
        plt.scatter(xs, ys, c=cs, s=400, cmap="PiYG_r")
        ax.set_yticklabels([])
        ax.set_xticklabels([])

        plt.colorbar()

        for (nid, x, y, z) in four:
            ax.annotate(str(nid), xy=(x, y), horizontalalignment='center', verticalalignment='center')

        plt.savefig("noise-floor-heatmap-{}.pdf".format(args.channel))

        if args.show:
            plt.show()

def main():
    parser = argparse.ArgumentParser(description="Testbed", add_help=True)

    parser.add_argument("testbed", type=str, help="The name of the testbed being profiled")
    parser.add_argument("topology", type=str, help="The testbed topology being used")
    parser.add_argument("--results-dir", type=str, help="The directory containing results for RSSI and signal measurements on the testbed", required=True)
    parser.add_argument("--flush", action="store_true", default=False)

    subparsers = parser.add_subparsers(title="action", dest="action")

    argument_handlers = {}

    def add_argument(name, fn, **kwargs):
        argument_handlers[name] = fn
        return subparsers.add_parser(name, **kwargs)

    processor = ResultsProcessor()

    subparser = add_argument("print-individual-rssi", processor.print_individual_rssi)
    subparser = add_argument("print-combined-rssi", processor.print_combined_rssi)
    subparser = add_argument("print-current-errors", processor.print_current_errors)
    subparser = add_argument("print-missing-results", processor.print_missing_results)
    subparser = add_argument("print-link-info", processor.print_link_info)

    subparser = add_argument("draw-link", processor.draw_link)
    subparser.add_argument("name", type=str, help="The name of the metric to draw", choices=["prr", "lqi", "rssi"])
    subparser.add_argument("power", type=int, help="The broadcast power level to show", choices=[3, 7, 11, 15, 19, 23, 27, 31])
    subparser.add_argument("--show", action="store_true", default=False)

    subparser = add_argument("draw-link-heatmap", processor.draw_link_heatmap)
    subparser.add_argument("--show", action="store_true", default=False)

    subparser = add_argument("draw-link-asymmetry-heatmap", processor.draw_link_asymmetry_heatmap)
    subparser.add_argument("--show", action="store_true", default=False)

    subparser = add_argument("draw-noise-floor-heatmap", processor.draw_noise_floor_heatmap)
    subparser.add_argument("channel", type=int, choices=[26])
    subparser.add_argument("--show", action="store_true", default=False)

    args = parser.parse_args(sys.argv[1:])

    processor.setup(args)

    argument_handlers[args.action](args)

if __name__ == "__main__":
    main()
