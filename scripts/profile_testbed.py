#!/usr/bin/env python3
from __future__ import print_function, division

import argparse
from collections import defaultdict
from datetime import datetime
import itertools
import os
import pickle
import re
import sys
import traceback

import numpy as np
import pandas as pd

from data.util import RunningStats
from data import submodule_loader
import data.testbed

import simulator.OfflineLogConverter as OfflineLogConverter

class RSSIResult(object):
    def __init__(self):
        self.node_average = defaultdict(RunningStats)
        self.node_smallest = defaultdict(RunningStats)
        self.node_largest = defaultdict(RunningStats)

        self.total_reads = defaultdict(int)

        self.start_time = None
        self.stop_time = None

    def add(self, date_time, kind, d_or_e, nid, localtime, details):
        if kind == "M-RSSI":
            (average, smallest, largest, reads, channel) = map(int, details.split(",", 4))

            self.node_average[(nid, channel)].push(average)
            self.node_smallest[(nid, channel)].push(smallest)
            self.node_largest[(nid, channel)].push(largest)

            self.total_reads[(nid, channel)] += reads

            if self.start_time is None:
                self.start_time = date_time

            if self.stop_time is None:
                self.stop_time = date_time

            if date_time > self.stop_time:
                self.stop_time = date_time

        else:
            return

    def combine(self, other):
        result = RSSIResult()

        keys = set(self.node_average.keys()) | set(other.node_average.keys())

        for key in keys:
            result.node_average[key] = self.node_average[key].combine(other.node_average[key])
            result.node_smallest[key] = self.node_smallest[key].combine(other.node_smallest[key])
            result.node_largest[key] = self.node_largest[key].combine(other.node_largest[key])

            result.total_reads[key] = self.total_reads[key] + other.total_reads[key]

        result.start_time = min(self.start_time, other.start_time)
        result.stop_time = max(self.stop_time, other.stop_time)

        return result

class LinkResult(object):
    def __init__(self):
        self.broadcasting_node_id = None
        self.broadcasts = 0
        self.broadcast_power = None

        self.deliver_at_rssi = defaultdict(RunningStats)
        self.deliver_at_lqi = defaultdict(RunningStats)

    def add(self, date_time, kind, d_or_e, nid, localtime, details):
        if kind == "M-CB":
            (msg_type, status, seq_no, tx_power) = details.split(",", 3)

            tx_power = int(tx_power)

            #print("Bcast ", seq_no)

            if self.broadcasting_node_id is None:
                self.broadcasting_node_id = nid
            elif self.broadcasting_node_id != nid:
                raise RuntimeError("Multiple nodes broadcasting")

            self.broadcasts += 1

            if self.broadcast_power is None:
                self.broadcast_power = tx_power
            elif self.broadcast_power != tx_power:
                raise RuntimeError("Multiple broadcast powers")

        elif kind == "M-CD":
            (msg_type, proximate_src, ultimate_src, seq_no, rssi, lqi) = details.split(",", 5)

            rssi = int(rssi)
            lqi = int(lqi)

            #print("Deliv ", seq_no, " rssi ", rssi, " lqi ", lqi)

            self.deliver_at_rssi[nid].push(rssi)
            self.deliver_at_lqi[nid].push(lqi)

        else:
            return

    def prr(self):
        return {
            nid: stats.count() / self.broadcasts
            for (nid, stats)
            in self.deliver_at_rssi.items()
        }

    def combine(self, other):
        if self.broadcasting_node_id != other.broadcasting_node_id:
            raise RuntimeError("Bad broadcasting_node_id")
        if self.broadcast_power != other.broadcast_power:
            raise RuntimeError("Bad broadcast_power")

        result = LinkResult()

        result.broadcasting_node_id = self.broadcasting_node_id
        result.broadcast_power = self.broadcast_power

        result.broadcasts = self.broadcasts + other.broadcasts

        for nid in set(self.deliver_at_rssi.keys()) | set(other.deliver_at_rssi.keys()):
            result.deliver_at_rssi[nid] = self.deliver_at_rssi[nid].combine(other.deliver_at_rssi[nid])
            result.deliver_at_lqi[nid] = self.deliver_at_lqi[nid].combine(other.deliver_at_lqi[nid])

        return result

class AnalyseTestbedProfile(object):

    _sanitise_match = re.compile(r"(\x00)+")

    def __init__(self, args):
        self._testbed_args = args.testbed

        testbed = self._get_testbed()

        self.testbed_name = testbed.name()
        self.testbed_result_file_name = testbed.result_file_name

        self.testbed_topology = getattr(testbed, args.topology)()

        self.flush = args.flush

    def _get_testbed(self):
        return submodule_loader.load(data.testbed, self._testbed_args)

    @classmethod
    def _sanitise_string(cls, input_string):
        return cls._sanitise_match.sub(r"\1..\1", input_string)

    def _get_result_path(self, results_dir):

        # Don't try this path if it is not a directory
        if not os.path.isdir(results_dir):
            return None

        for result_file_name in self.testbed_result_file_name:
            result_file = os.path.join(results_dir, result_file_name)

            if os.path.exists(result_file) and os.path.getsize(result_file) > 0:
                return result_file

        print("Unable to find any result file (greater than 0 bytes) in {} out of {}".format(
            results_dir, self.testbed_result_file_name)
        )

        return None

    def _parse_aggregation(self, results_dir):
        result_file = self._get_result_path(results_dir)

        if result_file is None:
            return None

        pickle_path = result_file + ".pickle"

        if os.path.exists(pickle_path) and not self.flush:

            print("Loading saved results from:", pickle_path)

            try:
                with open(pickle_path, 'rb') as pickle_file:
                    return pickle.load(pickle_file)
            except EOFError:
                print("Failed to load saved results from:", pickle_path)

        print("Processing results in:", result_file)

        converter = OfflineLogConverter.create_specific(self.testbed_name, result_file)

        # This file is of one of two types.
        # Either is is RSSI measurements, where no nodes are broadcasting.
        # Or, a single node is broadcasting and the rest and listening.
        result = self._analyse_log_file(converter)

        with open(pickle_path, 'wb') as pickle_file:
            pickle.dump(result, pickle_file, protocol=pickle.HIGHEST_PROTOCOL)

        return result

    def _parse_measurements(self, results_dir):
        testbed = self._get_testbed()

        # Check if testbed support measuring other values
        if not hasattr(testbed, "measurement_files") or not hasattr(testbed, "parse_measurement"):
            return None

        results = {}

        for measurement_file in testbed.measurement_files:

            measurement_path = os.path.join(results_dir, measurement_file)

            if not os.path.exists(measurement_path):
                continue

            pickle_path = measurement_path + ".pickle"

            if os.path.exists(pickle_path) and not self.flush:
                try:
                    with open(pickle_path, 'rb') as pickle_file:
                        results[measurement_file] = pickle.load(pickle_file)

                    continue

                except EOFError:
                    print("Failed to load saved results from:", pickle_path)

            results[measurement_file] = testbed.parse_measurement(measurement_path)

            with open(pickle_path, 'wb') as pickle_file:
                pickle.dump(results[measurement_file], pickle_file, protocol=pickle.HIGHEST_PROTOCOL)

        return results

    def _get_average_current_draw(self, measurement_results):
        if self.testbed_name == "flocklab":

            df = measurement_results["powerprofiling.csv"]
            df = df.groupby(["node_id"])["value_mA"].agg([np.mean, np.std]).reset_index()
            df.rename(columns={"node_id": "node"}, inplace=True)

            return df

        elif self.testbed_name == "fitiotlab":

            df = measurement_results["current.csv"]

            # Convert from amperes to mA
            df["current"] = df["current"] * 1000

            df = df.groupby(["node"])["current"].agg([np.mean, np.std]).reset_index()

            return df

        else:
            raise RuntimeError("Unknown testbed {}".format(self.testbed_name))


    def _do_run(self, results_dir):
        if not os.path.isdir(results_dir):
            return None

        result = self._parse_aggregation(results_dir)
        
        measurement_results = self._parse_measurements(results_dir)

        try:
            average_current_draw = self._get_average_current_draw(measurement_results)
        except KeyError:
            average_current_draw = None

        return result


    def run(self, args):
        files = [
            os.path.join(args.results_dir, result_folder)
            for result_folder
            in os.listdir(args.results_dir)
        ]

        return [x for x in map(self._do_run, files) if x is not None]

    def run_parallel(self, args):
        import multiprocessing

        files = [
            os.path.join(args.results_dir, result_folder)
            for result_folder
            in os.listdir(args.results_dir)
        ]

        job_pool = multiprocessing.Pool(processes=2)

        return [x for x in job_pool.map(self._do_run, files) if x is not None]

    def _process_line(self, line):
        try:
            (date_time, rest) = line.split("|", 1)

            date_time = datetime.strptime(date_time, "%Y/%m/%d %H:%M:%S.%f")

            (kind, d_or_e, nid, localtime, details) = rest.split(":", 4)
            nid = int(nid)
            localtime = int(localtime)

            return (date_time, kind, d_or_e, nid, localtime, details)
        except BaseException as ex:
            print("Failed to parse the line:", self._sanitise_string(line))
            print(self._sanitise_string(str(ex)))
            traceback.print_exc()

            return None

    def _analyse_log_file(self, converter):
        result = None

        for line in converter:

            line_result = self._process_line(line)
            if line_result is None:
                continue

            if result is None:
                kind, details = line_result[1], line_result[5]
                if kind == "stdout" and "An object has been detected" in details:
                    result = LinkResult()

                elif kind == "M-RSSI":
                    result = RSSIResult()

                else:
                    continue

            try:
                result.add(*line_result)
            except ValueError as ex:
                print("Failed to parse: ", self._sanitise_string(line))
                traceback.print_exc()
                continue

        return result

    def combine_link_results(self, results):
        labels = list(self.testbed_topology.nodes.keys())

        tx_powers = {result.broadcast_power for result in results}

        print(labels)

        rssi = {power: pd.DataFrame(np.full((len(labels), len(labels)), np.nan), index=labels, columns=labels) for power in tx_powers}
        lqi = {power: pd.DataFrame(np.full((len(labels), len(labels)), np.nan), index=labels, columns=labels) for power in tx_powers}
        prr = {power: pd.DataFrame(np.full((len(labels), len(labels)), np.nan), index=labels, columns=labels) for power in tx_powers}

        # Combine results by broadcast id
        combined_results = {
            (label, power): [result for result in results if result.broadcasting_node_id == label and result.broadcast_power == power]
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
                print((sender, power), "has", len(sender_results), "results")

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


        for power in sorted(tx_powers):
            print("For power level:", power)
            print("RSSI:\n", rssi[power])
            print("LQI:\n", lqi[power])
            print("PRR:\n", prr[power])
            print("")

        return rssi, lqi, prr

    def draw_prr(self, prr):
        import pygraphviz as pgv

        G = pgv.AGraph(strict=False, directed=True)

        labels = list(prr.columns.values)

        for label in labels:
            G.add_node(label)

        for index, row in prr.iterrows():
            for label in labels:
                if not np.isnan(row[label]):
                    G.add_edge(index, label, round(row[label], 2))

        G.layout()

        G.draw('prr.png')





def main():
    parser = argparse.ArgumentParser(description="Testbed", add_help=True)

    parser.add_argument("testbed", type=str, help="The name of the testbed being profiled")
    parser.add_argument("topology", type=str, help="The testbed topology being used")
    parser.add_argument("--results-dir", type=str, help="The directory containing results for RSSI and signal measurements on the testbed", required=True)
    parser.add_argument("--parallel", action="store_true", default=False)
    parser.add_argument("--flush", action="store_true", default=False)

    args = parser.parse_args(sys.argv[1:])

    analyse = AnalyseTestbedProfile(args)

    if not args.parallel:
        results = analyse.run(args)
    else:
        if sys.version_info.major < 3:
            raise RuntimeError("Parallel mode only supported with Python 3")

        results = analyse.run_parallel(args)

    rssi_results = [result for result in results if isinstance(result, RSSIResult)]
    link_results = sorted([result for result in results if isinstance(result, LinkResult)], key=lambda x: x.broadcasting_node_id)

    if len(rssi_results) == 0:
        raise RuntimeError("No RSSI results")
    if len(link_results) == 0:
        raise RuntimeError("No Link results")

    print("RSSI Results:")
    for result in rssi_results:
        for key in sorted(result.node_average.keys()):
            (nid, channel) = key
            print("Node", str(nid).rjust(4),
                  "channel", channel,
                  "rssi", "{:.2f}".format(result.node_average[key].mean()).rjust(6),
                  "+-", "{:.2f}".format(result.node_average[key].stddev())
            )


    rssi_iter = iter(rssi_results)

    rssi_result = next(rssi_iter)
    for result in rssi_iter:
        rssi_result = rssi_result.combine(result)

    print("Combined RSSI Result:")
    for key in sorted(rssi_result.node_average.keys()):
        (nid, channel) = key
        print("Node", str(nid).rjust(4),
              "channel", channel,
              "rssi", "{:.2f}".format(rssi_result.node_average[key].mean()).rjust(6),
              "+-", "{:.2f}".format(rssi_result.node_average[key].stddev())
        )

    rssi, lqi, prr = analyse.combine_link_results(link_results)

    tx_powers = {result.broadcast_power for result in link_results}

    link_bcast_nodes = {(result.broadcasting_node_id, result.broadcast_power) for result in link_results}
    missing_link_bcast_nodes = set(itertools.product(analyse.testbed_topology.nodes.keys(), tx_powers)) - link_bcast_nodes

    if len(missing_link_bcast_nodes) != 0:
        print("Missing the following link bcast results:")
        for node, power in missing_link_bcast_nodes:
            print("Node:", node, "Power:", power)

        print("Nodes:", list(node for (node, power) in missing_link_bcast_nodes))

    #analyse.draw_prr(prr)

if __name__ == "__main__":
    main()
