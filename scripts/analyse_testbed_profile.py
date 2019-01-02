#!/usr/bin/env python3

import argparse
from collections import defaultdict
import copy
import itertools
import math
import os.path
import pickle
import subprocess
import sys

import numpy as np
import pandas as pd

from data import submodule_loader
import data.testbed

from simulator.Topology import OrderedId

from scripts.profile_testbed import LinkResult, CurrentDraw, RSSIResult

min_max = {"prr": (0, 1), "rssi": (-95.5, -42.5), "lqi": (50, 110)}
asymmetry_min_max = {"prr": (-1, 1), "rssi": (-100, 100), "lqi": (-110, 110)}

class ResultsProcessor(object):

    results_path = "results.pickle"
    current_path = "current.pickle"
    link_path = "link.pickle"
    noise_floor_path = "noise_floor.pickle"

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

        if len(self.results) != len(self.rssi_results) + len(self.link_results) + len(self.current_results):
            raise RuntimeError("Unable to process some results")

        #if len(self.rssi_results) == 0:
        #    raise RuntimeError("No RSSI results")
        #if len(self.link_results) == 0:
        #    raise RuntimeError("No Link results")

    def _get_testbed(self):
        return submodule_loader.load(data.testbed, self.args.testbed)

    def _combine_current_summary(self, results):
        if len(results) == 0:
            raise RuntimeError("There are no items in results")

        labels = list(self.testbed_topology.nodes.keys())

        dfs = []

        # Get each result the sum of squares
        for result in results:
            df = result.summary_df if not isinstance(result, pd.DataFrame) else pd.DataFrame(result)

            if "var0" not in df and "std" in df:
                df["var0"] = df["std"]**2

            df["ss"] = df["var0"] * df["len"] + df["len"] * df["mean"]**2
            df["sum"] = df["mean"] * df["len"]

            if "node" in df:
                df = df.set_index("node")#.reindex(labels, fill_value=0)
            df = df[["len", "ss", "sum"]]

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
            key = (result.broadcasting_node_id, result.broadcast_power, result.channel)

            grouped_results[key].append(result)

            if result.bad_df is not None:
                bad_df_as_dict = result.bad_df.to_dict(orient='index')

                for value in bad_df_as_dict.values():
                    node = int(value[('node', '')])
                    count = int(value[('current', 'len')])

                    bad_nodes[node] += count

        combined_results = {}

        for (key, results) in grouped_results.items():
            combined_result = self._combine_current_summary(results)
            
            combined_results[key] = combined_result

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
        labels = [x.nid for x in self.testbed_topology.nodes.keys()]
        tx_powers = {result.broadcast_power for result in self.link_results}
        channels = {result.channel for result in self.link_results}

        #print(labels)

        def empty_label_grid(default=np.nan):
            return pd.DataFrame(np.full((len(labels), len(labels)), default), index=labels, columns=labels)

        rssi = {k: empty_label_grid() for k in itertools.product(tx_powers, channels)}
        lqi  = {k: empty_label_grid() for k in itertools.product(tx_powers, channels)}
        prr  = {k: empty_label_grid() for k in itertools.product(tx_powers, channels)}

        # Combine results by broadcast id
        combined_results = {
            (label, power, channel): [
                result
                for result
                in self.link_results
                if result.broadcasting_node_id == label
                and result.broadcast_power == power
                and result.channel == channel
            ]
            for label in labels
            for power in tx_powers
            for channel in channels
        }

        for (sender, power, channel), sender_results in combined_results.items():

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

            key = (power, channel)

            result_prr = result.prr()

            for other_nid in result.deliver_at_lqi:

                if sender not in labels or other_nid not in labels:
                    continue

                rssi[key].at[sender, other_nid] = result.deliver_at_rssi[other_nid].mean()
                lqi[key].at[sender, other_nid] = result.deliver_at_lqi[other_nid].mean()
                prr[key].at[sender, other_nid] = result_prr[other_nid]

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

            copy = df.fillna(value=np.nan)

            names = list(copy.columns.values)

            for (row, col) in itertools.product(names, repeat=2):

                left = df[row][col]
                right = df[col][row]

                if np.isnan(left) and np.isnan(right):
                    pass
                elif np.isnan(left) and not np.isnan(right):
                    copy.at[row, col] = +right
                elif not np.isnan(left) and np.isnan(right):
                    copy.at[row, col] = -left
                else:
                    copy.at[row, col] = right - left

            new_result[k] = copy

        return new_result

    def _get_combined_noise_floor(self):
        noise_floor_path = os.path.join(self.args.results_dir, self.noise_floor_path)

        if os.path.exists(noise_floor_path) and not self.args.flush:
            with open(noise_floor_path, 'rb') as pickle_file:
                return pickle.load(pickle_file)

        rssi_iter = iter(self.rssi_results)

        rssi_result = next(rssi_iter)
        for result in rssi_iter:
            rssi_result = rssi_result.combine(result)

        with open(noise_floor_path, 'wb') as pickle_file:
            pickle.dump(rssi_result, pickle_file, protocol=pickle.HIGHEST_PROTOCOL)

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

    def print_combined_current(self, args):
        combined_current, total_good_current, bad_current_nodes = self._get_combined_current_results()

        print(combined_current)

        #print("Good: ", total_good_current)
        print("Bad: ", bad_current_nodes)

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
        channels = {result.channel for result in self.link_results}

        with open("link-info.txt", "w") as link_info_file:
            with pd.option_context("display.max_rows", None, "display.max_columns", None, "expand_frame_repr", False):
                for (power, channel) in itertools.product(sorted(tx_powers), sorted(channels)):
                    print(f"For power level: {power} and Channel {channel}", file=link_info_file)
                    print("RSSI:\n", rssi[(power, channel)].round(2).replace(np.nan, ''), file=link_info_file)
                    print("LQI:\n", lqi[(power, channel)].round(2).replace(np.nan, ''), file=link_info_file)
                    print("PRR:\n", prr[(power, channel)].round(2).replace(np.nan, ''), file=link_info_file)
                    print("", file=link_info_file)

        print("Saved link info to link-info.txt")


    def _draw_link_heatmap_fn(self, args, heatmap_name, converter=lambda x: x, min_max=None, cmap=None, title_formatter=None):
        import matplotlib
        import matplotlib.pyplot as plt
        from matplotlib.ticker import MultipleLocator

        from mpl_toolkits.axes_grid1 import make_axes_locatable

        matplotlib.rcParams.update({'font.size': 16, 'figure.autolayout': True})

        plt.tight_layout()

        rssi, lqi, prr = map(converter, self._get_combined_link_results())

        nids = [nid.nid for nid in self.testbed_topology.nodes.keys()]
        tx_powers = {result.broadcast_power for result in self.link_results}
        channels = {result.channel for result in self.link_results}

        prr = {k: v * 100 for (k, v) in prr.items()}

        details = [("prr", prr, "%"), ("rssi", rssi, "dBm"), ("lqi", lqi, "")]

        for (power, channel) in itertools.product(sorted(tx_powers), sorted(channels)):
            for (i, (name, value, label)) in enumerate(details, start=1):

                if min_max is None:
                    vmin, vmax = None, None
                else:
                    vmin, vmax = min_max[name]

                if name == "prr":
                    vmin *= 100
                    vmax *= 100

                if args.combine:
                    ax = plt.subplot(1, len(details), i)
                else:
                    ax = plt.gca()


                # Check that we are within the bounds
                f = np.vectorize(lambda x: np.nan if vmin <= x <= vmax or np.isnan(x) else x)
                check = f(value[(power, channel)].values)

                if not np.isnan(check).all():
                    print(check)

                im = ax.imshow(value[(power, channel)], cmap=cmap, aspect="equal", origin="lower", vmin=vmin, vmax=vmax)

                ax.xaxis.set_ticks(range(len(nids)))
                ax.yaxis.set_ticks(range(len(nids)))
                ax.set_xticklabels(nids)
                ax.set_yticklabels(nids)
                ax.tick_params(axis='both', which='both', labelsize=11)

                for l in ax.xaxis.get_ticklabels()[1::2]:
                    l.set_visible(False)
                for l in ax.yaxis.get_ticklabels()[2::2]:
                    l.set_visible(False)

                title = title_formatter(name, label)

                plt.title(title)
                plt.ylabel("Sender")
                plt.xlabel("Receiver")

                #plt.yticks(range(len(value[power].index)), value[power].index, size='xx-small')
                #plt.xticks(range(len(value[power].columns)), value[power].columns, size='xx-small')

                divider = make_axes_locatable(ax)
                cax = divider.append_axes("right", size="5%", pad=0.05)
                cb = plt.colorbar(im, cax=cax)
                cb.ax.tick_params(labelsize=12)

                #plt.xlim(min(df.columns), max(df.columns))
                #plt.ylim(min(df.index), max(df.index))

                if not args.combine:

                    filename = f"{heatmap_name}-heatmap-{name}-{power}-{channel}.pdf"

                    plt.savefig(filename)

                    subprocess.check_call(["pdfcrop", filename, filename])

                    plt.clf()

            if args.combine:
                plt.subplots_adjust(wspace=0.35)

                plt.savefig("heatmap-{}.pdf".format(power))

                if args.show:
                    plt.show()

            plt.clf()

    def draw_link_heatmap(self, args):
        return self._draw_link_heatmap_fn(args, "link",
            min_max=min_max,
            cmap="PiYG",
            title_formatter=lambda name, label: f"{name.upper()}" if not label else f"{name.upper()} ({label})"
        )

    def draw_link_asymmetry_heatmap(self, args):
        return self._draw_link_heatmap_fn(args, "asymmetry-link",
            converter=self._get_link_asymmetry_results,
            min_max=asymmetry_min_max,
            cmap="bwr",
            title_formatter=lambda name, label: f"{name.upper()} Difference" if not label else f"{name.upper()} Difference ({label})"
        )

    def draw_link(self, args):
        import matplotlib.colors as colors
        import matplotlib.cm as cmx

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
            raise RuntimeError(f"Unknown name {args.name}")

        try:
            result = result[(args.power, args.channel)]
        except KeyError:
            raise RuntimeError("No result for {} with power {}".format(args.name, args.power))

        labels = list(result.columns.values)

        cmap = cmx.get_cmap("RdYlGn")
        cnorm  = colors.Normalize(vmin=min_max[args.name][0], vmax=min_max[args.name][1])
        scalarmap = cmx.ScalarMappable(norm=cnorm, cmap=cmap)


        G = nx.MultiDiGraph()
        G.add_nodes_from(labels)

        target_width_pixels = 1024

        xs = [coord[0] for coord in self.testbed_topology.nodes.values()]

        scale = target_width_pixels / (max(xs) - min(xs))

        for node in G:
            coords = self.testbed_topology.nodes[OrderedId(node)]

            x, y = coords[0], coords[1]

            G.node[node]['pos'] = f"{x*scale},{y*scale}"
            G.node[node]['fontsize'] = "36"
            G.node[node]['fixedsize'] = "true"
            G.node[node]['width'] = "0.8"
            G.node[node]['height'] = "0.8"

        for node1, row in result.iterrows():
            for node2 in labels:
                if not np.isnan(row[node2]):
                    if args.threshold is None or row[node2] >= args.threshold:
                        G.add_edge(node1, node2,
                            label=round(row[node2], 2),
                            color=colors.rgb2hex(scalarmap.to_rgba(row[node2])),
                            fontsize="22"
                        )

        dot_path = f"{args.name}-{args.power}.dot"
        pdf_path = dot_path.replace(".dot", ".pdf")

        write_dot(G, dot_path)

        subprocess.check_call(f"neato -n2 -Gdpi=500 -T pdf {dot_path} -o {pdf_path}", shell=True)

        subprocess.check_call(["pdfcrop", pdf_path, pdf_path])

        if args.show:
            subprocess.call(f"xdg-open {pdf_path}", shell=True)

    def draw_noise_floor_heatmap(self, args):
        import matplotlib.pyplot as plt

        noise_floor = self._get_combined_noise_floor()

        z = {
            nid: result.mean()
            for ((nid, channel), result)
            in noise_floor.node_average.items()
            if channel == args.channel
        }

        node_info = [
            (nid, coord, z[nid.nid])
            for (nid, coord)
            in self.testbed_topology.nodes.items()
            if nid.nid in z
        ]

        n, coords, cs = zip(*node_info)

        xs = [coord[0] for coord in coords]
        ys = [coord[1] for coord in coords]

        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)

        #vmin, vmax = -100, -83
        vmin, vmax = -98, -92

        try:
            zs = [coord[2] for coord in coords]
        except IndexError:
            zs = None

        if zs is None:
            rangex, rangey = max(xs) - min(xs), max(ys) - min(ys)

            scale = 8

            fig, ax = plt.subplots(figsize=(scale * (rangex / rangex), scale * (rangey / rangex)))

            plt.scatter(xs, ys, c=cs, s=400, cmap="binary", vmin=vmin, vmax=vmax)
            ax.set_yticklabels([])
            ax.set_xticklabels([])

            ax.set_aspect('equal', 'datalim')

            plt.colorbar()

            for (nid, coord, c) in node_info:
                ax.annotate(str(nid), xy=(coord[0], coord[1]), horizontalalignment='center', verticalalignment='center')

            path = f"noise-floor-heatmap-{args.channel}.pdf"
            plt.savefig(path)

            subprocess.check_call(["pdfcrop", path, path])

            if args.show:
                plt.show()

        else:
            grouped_xy = defaultdict(list)

            for (x, y, z, c) in zip(xs, ys, zs, cs):
                grouped_xy[z].append((x, y, c))

            fig, axes = plt.subplots(nrows=4, ncols=int(math.ceil(len(grouped_xy)/4)), figsize=(math.sqrt(2) * 20, 1 * 20))

            for ((i, (z, xys)), ax) in zip(enumerate(sorted(grouped_xy.items(), key=lambda x: x[0]), start=1), axes.flat):
                xs = [xy[0] for xy in xys]
                ys = [xy[1] for xy in xys]
                cs = [xy[2] for xy in xys]

                im = ax.scatter(xs, ys, c=cs, s=400, cmap="binary", vmin=vmin, vmax=vmax)
                ax.set_yticklabels([])
                ax.set_xticklabels([])

                adjust = 0.5

                ax.set_xlim([minx-adjust, maxx+adjust])
                ax.set_ylim([miny-adjust, maxy+adjust])

                ax.set_title("z={}m".format(z))

                for (nid, coord, c) in node_info:
                    if np.isclose(coord[2], z):
                        ax.annotate(str(nid), xy=(coord[0], coord[1]), horizontalalignment='center', verticalalignment='center')

            fig.subplots_adjust(right=0.8)
            cbar_ax = plt.gcf().add_axes([0.85, 0.15, 0.05, 0.7])
            fig.colorbar(im, cax=cbar_ax)

            path = "noise-floor-heatmap-{}.pdf".format(args.channel)
            plt.savefig(path)

            subprocess.check_call(["pdfcrop", path, path])

            if args.show:
                plt.show()

    def draw_noise_floor_graph(self, args):
        import matplotlib as mpl
        import matplotlib.pyplot as plt

        noise_floor = self._get_combined_noise_floor()

        data = {}
        for ((nid, channel), result) in noise_floor.node_average.items():
            data[(nid, channel)] = (result.mean(), result.stddev())

        node_ids = [
            nid.nid
            for (nid, coord)
            in self.testbed_topology.nodes.items()
        ]

        channels = list(range(11, 27))

        fig, axs = plt.subplots(ncols=3, nrows=math.ceil(len(node_ids)/3), figsize=(7.0056, 4))

        real_vmin, real_vmax = min(v[0] for (k, v) in data.items()), max(v[0] for (k, v) in data.items())

        vmin, vmax = -100, -80

        if real_vmin < vmin:
            raise RuntimeError("Bad vmin {} < {}".format(real_vmin, vmin))
        if real_vmax > vmax:
            raise RuntimeError("Bad vmax {} > {}".format(real_vmax, vmax))


        for nid, ax in zip(node_ids, axs.flat):
            xs = channels
            ys = [data[(nid, x)][0] if (nid, x) in data else float('NaN') for x in xs]
            es = [data[(nid, x)][1] if (nid, x) in data else float('NaN') for x in xs]

            ax.set_title(str(nid), rotation='horizontal', x=-0.1, y=-0.5)

            #ax.scatter(xs, ys, label=str(nid))
            #ax.errorbar(xs, ys, yerr=es, label=str(nid), linestyle="None")

            hm = [ys]

            im = ax.imshow(hm, cmap="binary", interpolation='none', vmin=vmin, vmax=vmax)
            ax.set_aspect(1.5)
            ax.set_xticks(range(len(xs)))
            ax.set_xticklabels(xs)

            for label in ax.xaxis.get_ticklabels()[::2]:
                label.set_visible(False)

            ax.tick_params(
                axis='y',
                which='both',
                left=False,
                right=False,
                labelleft=False)
            ax.tick_params(axis='both', which='major', labelsize=8)
            ax.tick_params(axis='both', which='minor', labelsize=8)

        plt.tight_layout()

        cax, kw = mpl.colorbar.make_axes([ax for ax in axs.flat])
        cb = plt.colorbar(im, cax=cax, **kw)
        cb.ax.tick_params(labelsize=10)

        path = "noise-floor-graph.pdf"
        plt.savefig(path)

        subprocess.check_call(["pdfcrop", path, path])

        if args.show:
            plt.show()

    def draw_combined_current_graph(self, args):
        import matplotlib as mpl
        import matplotlib.pyplot as plt

        def other_get_combined_current_results(name):
            processor = ResultsProcessor()
            a = copy.deepcopy(self.args)
            a.results_dir = os.path.join(os.path.dirname(a.results_dir), name)
            print(a.results_dir)
            processor.setup(a)
            return processor._get_combined_current_results()

        combined_current_empty, _, _ = self._get_combined_current_results()
        combined_current_rssi, _, _ = other_get_combined_current_results("_read_rssi")
        ccp, _, _ = other_get_combined_current_results("noforward")

        channels = [26]
        tx_powers = [7, 19, 31]

        fig, (ax, ax2) = plt.subplots(2, 1, sharex=True, figsize=(7.0056, 3.5), gridspec_kw = {'height_ratios':[4, 1]})

        xs = [x.nid for x in self.testbed_topology.nodes.keys()]
        xns = np.arange(len(xs))
        xmap = dict(zip(xs, xns))

        # Separate
        """
        # Get only the Txing results
        d = {(txp, ch): [
                ccp[(x, txp, ch)][ccp[(x, txp, ch)].index == x]
                for x in xs
                if (x, txp, ch) in ccp
            ]
            for txp in tx_powers
            for ch in channels
        }
        combined_current_txing = {k: pd.concat(v) for (k, v) in d.items()}

        # Get only the Rxing results
        d = {(txp, ch): [
                ccp[(x, txp, ch)][ccp[(x, txp, ch)].index != x]
                for x in xs
                if (x, txp, ch) in ccp
            ]
            for txp in tx_powers
            for ch in channels
        }
        combined_current_rxing = {k: self._combine_current_summary(v) for (k, v) in d.items()}
        """

        # Combined
        # Get only the Txing results
        d = {(None, None, None): [
                ccp[(x, txp, ch)][ccp[(x, txp, ch)].index == x]
                for x in xs
                for txp in tx_powers
                for ch in channels
                if (x, txp, ch) in ccp
            ]
        }
        combined_current_txing = {k: pd.concat(v) for (k, v) in d.items()}

        # Get only the Rxing results
        d = {(None, None, None): [
                ccp[(x, txp, ch)][ccp[(x, txp, ch)].index != x]
                for x in xs
                for txp in tx_powers
                for ch in channels
                if (x, txp, ch) in ccp
            ]
        }
        combined_current_rxing = {k: self._combine_current_summary(v) for (k, v) in d.items()}

        ccs = {
            "Nothing": combined_current_empty,
            "RSSI": combined_current_rssi,
            "Tx": combined_current_txing,
            "Rx": combined_current_rxing,
        }

        print("Differences:")

        m1 = combined_current_rssi[(None, None, None)]["mean"]
        print("RSSI", np.max(m1) - np.min(m1))

        m1 = combined_current_rxing[(None, None, None)]["mean"]
        print("RX", np.max(m1) - np.min(m1))

        for a in (ax, ax2):
            for (name, cc) in ccs.items():

                for (key, df) in cc.items():
                    xs_local = [xmap[x] for x in df.index if x in xmap]
                    ys = df["mean"][[x in xmap for x in df.index]]
                    es = df["std"][[x in xmap for x in df.index]]

                    if key is None or all(k is None for k in key):
                        label = name
                    else:
                        label = f"{name} PTx:{key[0]} Ch:{key[1]}"

                    a.scatter(xs_local, ys, label=label)
                    a.errorbar(xs_local, ys, yerr=es, label=label, linestyle="None")

        ax.set_xticks(xns)
        ax.set_xticklabels(xs)

        ax2.set_ylim(0, 1)
        ax.set_ylim(18, 22)

        cax = fig.add_subplot(111)

        
        cax.set_frame_on(False)
        cax.tick_params(labelleft=False, labelbottom=False, left=False, bottom=False)
        cax.set_ylabel("Average Current Draw (mA)", labelpad=35)

        ax2.set_xlabel("Node IDs")

        # From: https://matplotlib.org/2.0.2/examples/pylab_examples/broken_axis.html

        # hide the spines between ax and ax2
        ax.spines['bottom'].set_visible(False)
        ax2.spines['top'].set_visible(False)
        ax.xaxis.tick_top()
        ax.tick_params(labeltop='off')  # don't put tick labels at the top
        ax2.xaxis.tick_bottom()

        #plt.tick_params(axis='both', which='major', labelsize=8)
        #plt.tick_params(axis='both', which='minor', labelsize=8)

        # This looks pretty good, and was fairly painless, but you can get that
        # cut-out diagonal lines look with just a bit more work. The important
        # thing to know here is that in axes coordinates, which are always
        # between 0-1, spine endpoints are at these locations (0,0), (0,1),
        # (1,0), and (1,1).  Thus, we just need to put the diagonals in the
        # appropriate corners of each of our axes, and so long as we use the
        # right transform and disable clipping.

        d = .015  # how big to make the diagonal lines in axes coordinates
        # arguments to pass to plot, just so we don't keep repeating them
        kwargs = dict(transform=ax.transAxes, color='k', clip_on=False)
        ax.plot((-d, +d), (-d, +d), **kwargs)        # top-left diagonal
        ax.plot((1 - d, 1 + d), (-d, +d), **kwargs)  # top-right diagonal

        kwargs.update(transform=ax2.transAxes)  # switch to the bottom axes
        ax2.plot((-d, +d), (1 - d, 1 + d), **kwargs)  # bottom-left diagonal
        ax2.plot((1 - d, 1 + d), (1 - d, 1 + d), **kwargs)  # bottom-right diagonal

        handles, labels = ax.get_legend_handles_labels()
        d = {h: l for (h, l) in zip(handles, labels) if isinstance(h, mpl.collections.PathCollection)}
        ax2.legend(d.keys(), d.values(), ncol=len(d.keys()), loc="upper center", bbox_to_anchor=(0.5, 1.6))

        plt.tight_layout()

        path = "energy-graph.pdf"
        plt.savefig(path)

        subprocess.check_call(["pdfcrop", path, path])

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

    def add_argument(name, fn, *args, **kwargs):
        argument_handlers[name] = fn
        return subparsers.add_parser(name, *args, **kwargs)

    processor = ResultsProcessor()

    subparser = add_argument("print-individual-rssi", processor.print_individual_rssi)
    subparser = add_argument("print-combined-rssi", processor.print_combined_rssi)
    subparser = add_argument("print-combined-current", processor.print_combined_current)
    subparser = add_argument("print-current-errors", processor.print_current_errors)
    subparser = add_argument("print-missing-results", processor.print_missing_results)
    subparser = add_argument("print-link-info", processor.print_link_info)

    subparser = add_argument("draw-link", processor.draw_link)
    subparser.add_argument("name", type=str, help="The name of the metric to draw", choices=["prr", "lqi", "rssi"])
    subparser.add_argument("power", type=int, help="The broadcast power level to show", choices=[3, 7, 11, 15, 19, 23, 27, 31])
    subparser.add_argument("channel", type=int, help="The channel", choices=range(11,27))
    subparser.add_argument("--show", action="store_true", default=False)
    subparser.add_argument("--threshold", type=float, default=None, help="The minimum value to show")

    subparser = add_argument("draw-link-heatmap", processor.draw_link_heatmap)
    subparser.add_argument("--show", action="store_true", default=False)
    subparser.add_argument("--combine", action="store_true", default=False)

    subparser = add_argument("draw-link-asymmetry-heatmap", processor.draw_link_asymmetry_heatmap)
    subparser.add_argument("--show", action="store_true", default=False)
    subparser.add_argument("--combine", action="store_true", default=False)

    subparser = add_argument("draw-noise-floor-heatmap", processor.draw_noise_floor_heatmap)
    subparser.add_argument("channel", type=int, choices=range(11, 27))
    subparser.add_argument("--show", action="store_true", default=False)

    subparser = add_argument("draw-noise-floor-graph", processor.draw_noise_floor_graph)
    subparser.add_argument("--show", action="store_true", default=False)

    subparser = add_argument("draw-combined-current-graph", processor.draw_combined_current_graph)
    subparser.add_argument("--show", action="store_true", default=False)

    args = parser.parse_args(sys.argv[1:])

    processor.setup(args)

    argument_handlers[args.action](args)

if __name__ == "__main__":
    main()
