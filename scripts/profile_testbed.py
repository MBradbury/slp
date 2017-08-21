#!/usr/bin/env python
from __future__ import print_function, division

import argparse
from collections import defaultdict
from datetime import datetime
import os
import sys

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

def process_line(line):
    try:
        (date_time, rest) = line.split("|", 1)

        date_time = datetime.strptime(date_time, "%Y/%m/%d %H:%M:%S.%f")

        (kind, d_or_e, nid, localtime, details) = rest.split(":", 4)
        nid = int(nid)
        localtime = int(localtime)

        return (date_time, kind, d_or_e, nid, localtime, details)
    except BaseException as ex:
        print("Failed to parse the line: ", line)
        raise

def analyse_log_file(converter):
    result = None

    for line in converter:

        (date_time, kind, d_or_e, nid, localtime, details) = process_line(line)
        
        if result is None:
            if kind == "stdout" and "An object has been detected" in details:
                result = LinkResult()

            elif kind == "M-RSSI":
                result = RSSIResult()

        if result is not None:
            try:
                result.add(date_time, kind, d_or_e, nid, localtime, details)
            except ValueError:
                print("Failed to parse: ", line)
                raise

    return result


def run_analyse_testbed_profile(args):
    testbed = submodule_loader.load(data.testbed, args.testbed)

    testbed_topology = getattr(testbed, args.topology)

    results = []

    for result_folder in os.listdir(args.results_dir):

        result_file = os.path.join(args.results_dir, result_folder, testbed.result_file_name)

        print("Processing results in:", result_file)

        converter = OfflineLogConverter.create_specific(args.testbed, result_file)

        # This file is of one of two types.
        # Either is is RSSI measurements, where no nodes are broadcasting.
        # Or, a single node is broadcasting and the rest and listening.
        results.append(analyse_log_file(converter))

    return results


def main():
    parser = argparse.ArgumentParser(description="Testbed", add_help=True)

    parser.add_argument("testbed", type=str, help="The name of the testbed being profiled")
    parser.add_argument("topology", type=str, help="The testbed topology being used")
    parser.add_argument("--results-dir", type=str, help="The directory containing results for RSSI and signal measurements on the testbed", required=True)

    args = parser.parse_args(sys.argv[1:])

    results = run_analyse_testbed_profile(args)

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

if __name__ == "__main__":
    main()
