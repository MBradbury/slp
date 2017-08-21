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
    (date_time, rest) = line.split("|", 1)

    date_time = datetime.strptime(date_time, "%Y/%m/%d %H:%M:%S.%f")

    (kind, d_or_e, nid, localtime, details) = rest.split(":", 4)
    nid = int(nid)
    localtime = int(localtime)

    return (date_time, kind, d_or_e, nid, localtime, details)

def analyse_log_file(converter):
    result = None

    for (date_time, kind, d_or_e, nid, localtime, details) in map(process_line, converter):
        
        if result is None:
            if kind == "stdout" and "An object has been detected" in details:
                result = LinkResult()

            elif kind == "M-RSSI":
                result = RSSIResult()

        if result is not None:
            result.add(date_time, kind, d_or_e, nid, localtime, details)

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

    run_analyse_testbed_profile(args)

if __name__ == "__main__":
    main()
