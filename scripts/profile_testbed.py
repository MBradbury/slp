#!/usr/bin/env python3
from __future__ import print_function, division

import argparse
from collections import defaultdict
from datetime import datetime
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

class AnalyseTestbedProfile(object):

    _sanitise_match = re.compile(r"(\x00)+")

    def __init__(self, args):
        testbed = submodule_loader.load(data.testbed, args.testbed)

        self.testbed_name = testbed.name()
        self.testbed_result_file_name = testbed.result_file_name

        self.testbed_topology = getattr(testbed, args.topology)()

        self.flush = args.flush

    @classmethod
    def _sanitise_string(cls, input_string):
        return cls._sanitise_match.sub(r"\1..\1", input_string)

    def _get_result_path(self, results_dir, result_folder):

        # Don't try this path if it is not a directory
        if not os.path.isdir(os.path.join(results_dir, result_folder)):
            return None

        for result_file_name in self.testbed_result_file_name:
            result_file = os.path.join(results_dir, result_folder, result_file_name)

            if os.path.exists(result_file) and os.path.getsize(result_file) > 0:
                return result_file

        print("Unable to find any result file (greater than 0 bytes) in {} out of {}".format(
            os.path.join(results_dir, result_folder),
            self.testbed_result_file_name)
        )

        return None

    def _do_run(self, result_file):

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


    def run(self, args):
        files = [
            x for x in
            (self._get_result_path(args.results_dir, result_folder) for result_folder in os.listdir(args.results_dir))
            if x is not None
        ]

        return list(map(self._do_run, files))

    def run_parallel(self, args):
        import multiprocessing

        files = [
            x for x in
            (self._get_result_path(args.results_dir, result_folder) for result_folder in os.listdir(args.results_dir))
            if x is not None
        ]

        job_pool = multiprocessing.Pool(processes=2)

        return job_pool.map(self._do_run, files)

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

        print(labels)

        rssi = pd.DataFrame(np.full((len(labels), len(labels)), np.nan), index=labels, columns=labels)
        lqi = pd.DataFrame(np.full((len(labels), len(labels)), np.nan), index=labels, columns=labels)
        prr = pd.DataFrame(np.full((len(labels), len(labels)), np.nan), index=labels, columns=labels)

        for result in results:
            sender = result.broadcasting_node_id
            result_prr = result.prr()

            for other_nid in result.deliver_at_lqi:

                if sender not in labels or other_nid not in labels:
                    continue

                rssi.set_value(sender, other_nid, result.deliver_at_rssi[other_nid].mean())
                lqi.set_value(sender, other_nid, result.deliver_at_lqi[other_nid].mean())
                prr.set_value(sender, other_nid, result_prr[other_nid])


        print("RSSI:\n", rssi)
        print("LQI:\n", lqi)
        print("PRR:\n", prr)

        return rssi, lqi, prr


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

    link_result = analyse.combine_link_results(link_results)

    link_bcast_nodes = {result.broadcasting_node_id for result in link_results}
    missing_link_bcast_nodes = set(analyse.testbed_topology.nodes.keys()) - link_bcast_nodes

    print("Missing the following link bcast results:")
    for node in missing_link_bcast_nodes:
        print(node)

if __name__ == "__main__":
    main()
