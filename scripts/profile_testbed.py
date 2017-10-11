#!/usr/bin/env python3

import argparse
from collections import defaultdict
from datetime import datetime
from functools import partial
import itertools
import os
import pickle
import re
import sys
import traceback

import numpy as np
import pandas as pd

from data.util import RunningStats
from data.progress import Progress
from data import submodule_loader
import data.testbed

import simulator.OfflineLogConverter as OfflineLogConverter

def var0(x):
    return np.var(x, ddof=0)

# (ref. http://www-mtl.mit.edu/Courses/6.111/labkit/datasheets/CC2420.pdf page 49)
RSSI_OFFSET = 45

def _adjust_tinyos_raw_rssi(rssi):
    # TinyOS RSSI measurements are in a raw form.
    # We must first take away 127 to get to the value
    # provided by the CC2420 chip (ref. CC2420ControlP.nc)
    # Next we must take away the RSSI_OFFSET (-45)
    # (ref. http://www-mtl.mit.edu/Courses/6.111/labkit/datasheets/CC2420.pdf page 49)
    return rssi - 127 - RSSI_OFFSET

def _adjust_tinyos_rssi(rssi):
    return rssi - RSSI_OFFSET

class UnknownTestbedError(RuntimeError):
    def __init__(self, testbed):
        super(UnknownTestbedError, self).__init__("Unknown testbed {}".format(testbed))

class RSSIResult(object):
    def __init__(self):
        self.node_average = {}
        #self.node_smallest = defaultdict(RunningStats)
        #self.node_largest = defaultdict(RunningStats)

        self.total_reads = {}

        #self.start_time = None
        #self.stop_time = None

    def add(self, date_time, kind, d_or_e, nid, localtime, details):
        if kind == "M-RSSI":
            (average, smallest, largest, reads, channel) = map(int, details.split(",", 4))

            key = (nid, channel)

            if key not in self.node_average:
                self.node_average[key] = RunningStats()
                self.total_reads[key] = 0

            average = _adjust_tinyos_raw_rssi(average)
            #smallest = _adjust_tinyos_raw_rssi(smallest)
            #largest = _adjust_tinyos_raw_rssi(largest)

            self.node_average[key].push(average)
            #self.node_smallest[(nid, channel)].push(smallest)
            #self.node_largest[(nid, channel)].push(largest)

            self.total_reads[key] += reads

            #if self.start_time is None:
            #    self.start_time = date_time

            #if self.stop_time is None:
            #    self.stop_time = date_time

            #if date_time > self.stop_time:
            #    self.stop_time = date_time

        else:
            return

    def combine(self, other):
        result = RSSIResult()

        keys = set(self.node_average.keys()) | set(other.node_average.keys())

        for key in keys:
            result.node_average[key] = self.node_average[key].combine(other.node_average[key])
            #result.node_smallest[key] = self.node_smallest[key].combine(other.node_smallest[key])
            #result.node_largest[key] = self.node_largest[key].combine(other.node_largest[key])

            result.total_reads[key] = self.total_reads[key] + other.total_reads[key]

        #result.start_time = min(self.start_time, other.start_time)
        #result.stop_time = max(self.stop_time, other.stop_time)

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

            rssi = _adjust_tinyos_rssi(int(rssi))
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

class CurrentDraw(object):
    def __init__(self, summary_df, bad_df=None, broadcasting_node_id=None):
        self.broadcasting_node_id = broadcasting_node_id
        self.summary_df = summary_df
        self.bad_df = bad_df

class AnalyseTestbedProfile(object):

    _sanitise_match = re.compile(r"(\x00)+")

    def __init__(self, args):
        self._testbed_args = args.testbed

        testbed = self._get_testbed()

        self.testbed_name = testbed.name()
        self.testbed_result_file_name = testbed.result_file_name

        self.testbed_topology = getattr(testbed, args.topology)()

        self.flush = args.flush

        self._job_counter = 0

    def _get_testbed(self):
        return submodule_loader.load(data.testbed, self._testbed_args)

    @classmethod
    def _sanitise_string(cls, input_string):
        return cls._sanitise_match.sub(r"\1..\1", input_string)

    def _get_result_path(self, results_dir):

        # Don't try this path if it is not a directory
        if not os.path.isdir(results_dir):
            return None

        result_file = os.path.join(results_dir, self.testbed_result_file_name)

        if os.path.exists(result_file) and os.path.getsize(result_file) > 0:
            return result_file

        print("Unable to find any result file (greater than 0 bytes) in {} out of {}".format(
            results_dir, self.testbed_result_file_name)
        )

        return None

    def _check_big_nul_file(self, result_path):
        with open(result_path, 'rb') as result_file:
            firstn = result_file.read(1024)

            ratio = sum(x == 0 for x in firstn) / len(firstn)

            if ratio >= 0.5:
                raise RuntimeError("File ({}) consists of NUL bytes ({}), skipping it".format(result_path, ratio))

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

        try:
            self._check_big_nul_file(result_file)
        except RuntimeError as ex:
            print(ex)
            return None

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

            if not os.path.exists(measurement_path) and not os.path.exists(measurement_path + ".gz"):
                continue

            pickle_path = measurement_path + ".pickle"

            if os.path.exists(pickle_path) and not self.flush:
                try:
                    with open(pickle_path, 'rb') as pickle_file:
                        results[measurement_file] = pickle.load(pickle_file)

                    continue

                except (EOFError, OSError):
                    print("Failed to load saved results from:", pickle_path)

            results[measurement_file] = testbed.parse_measurement(measurement_path)

            with open(pickle_path, 'wb') as pickle_file:
                pickle.dump(results[measurement_file], pickle_file, protocol=pickle.HIGHEST_PROTOCOL)

        return results

    def _get_average_current_draw(self, results_dir, measurement_results, broadcasting_node_id):

        pickle_path = os.path.join(results_dir, "current.pickle")

        if os.path.exists(pickle_path) and not self.flush:
            print("Loading saved current results from:", pickle_path)
            try:
                with open(pickle_path, 'rb') as pickle_file:
                    return pickle.load(pickle_file)
            except EOFError:
                print("Failed to load saved current results from:", pickle_path)

        if self.testbed_name == "flocklab":

            raw_df = measurement_results["powerprofiling.csv"]
            raw_df.rename(columns={"node_id": "node", "value_mA": "I"}, inplace=True)

            df = raw_df.groupby("node")["I"].agg([np.mean, var0, len]).reset_index()

            result = CurrentDraw(df, broadcasting_node_id=broadcasting_node_id)

        elif self.testbed_name == "fitiotlab":

            df = measurement_results["current.csv"]
            df = df.merge(measurement_results["power.csv"], on=["node", "time"])
            df = df.merge(measurement_results["voltage.csv"], on=["node", "time"])

            # times 1000 to convert from amperes to mA

            df["I"] = (df["power"] / df["voltage"]) * 1000
            df["current"] *= 1000

            # Power, current and voltage should not be negative
            # If they are something has gone wrong

            neg = df[["current", "I"]] < 0
            neg_eq2 = neg.apply(np.sum, axis='columns', raw=True) == 2

            removed_df = df[neg_eq2]   # Bad results with two negative results
            filtered_df = df[~neg_eq2].copy() # Recoverable results with zero or one negative result(s)

            filtered_df.loc[filtered_df.current < 0,   'I_2'] = filtered_df.I
            filtered_df.loc[filtered_df.I < 0,         'I_2'] = filtered_df.current
            filtered_df.loc[np.isnan(filtered_df.I_2), 'I_2'] = (filtered_df.current + filtered_df.I) / 2

            raw_df = filtered_df[["node", "time", "I_2"]].rename(columns={"I_2": "I"})

            df = raw_df.groupby("node")["I"].agg([np.mean, var0, len]).reset_index()
            removed_df = removed_df.groupby(["node"])["current", "voltage", "power"].agg([np.mean, np.std, len]).reset_index()

            result = CurrentDraw(df, bad_df=removed_df, broadcasting_node_id=broadcasting_node_id)

        else:
            raise UnknownTestbedError(self.testbed_name)

        with open(pickle_path, 'wb') as pickle_file:
            pickle.dump(result, pickle_file, protocol=pickle.HIGHEST_PROTOCOL)

        return result

    def _get_rssi(self, measurement_results):
        if self.testbed_name == "fitiotlab":

            df = measurement_results["rssi.csv"]
            df = df.groupby(["node"])["rssi"].agg([np.mean, var0, len]).reset_index()

            channel = None

            result = RSSIResult()

            for row in df.itertuples():
                result.node_average[(row.node, channel)].n = int(row.len)
                result.node_average[(row.node, channel)].new_m = float(row.mean)
                result.node_average[(row.node, channel)].new_s = float(row.var0) * int(row.len)

                result.total_reads[(row.node, channel)] = int(row.len)

            return result

        else:
            raise UnknownTestbedError(self.testbed_name)


    def _do_run(self, results_dir, progress):
        if not os.path.isdir(results_dir):
            return None

        result = self._parse_aggregation(results_dir)
        if result is None:
            return None
        
        measurement_results = self._parse_measurements(results_dir)

        try:
            if hasattr(result, "broadcasting_node_id"):
                broadcasting_node_id = result.broadcasting_node_id
            else:
                broadcasting_node_id = None

            average_current_draw = self._get_average_current_draw(results_dir, measurement_results, broadcasting_node_id)

        except (KeyError, UnknownTestbedError):
            average_current_draw = None

        # Some testbeds can record the RSSI during the execution of the application
        # If so, lets get those results and include them
        #try:
        #    rssi_extra = self._get_rssi(measurement_results)
        #except (KeyError, UnknownTestbedError):
        #    rssi_extra = None

        if progress is not None:
            progress.print_progress(self._job_counter)

            self._job_counter += 1

        return result, average_current_draw#, rssi_extra

    def _run(self, args, map_fn):
        files = [
            os.path.join(args.results_dir, result_folder)
            for result_folder
            in os.listdir(args.results_dir)
        ]

        if map_fn is map:
            progress = Progress("run")
            progress.start(len(files))
        else:
            progress = None

        fn = partial(self._do_run, progress=progress)

        return [
            x
            for l in map_fn(fn, files)
            if l is not None
            for x in l
            if x is not None
        ]

    def run(self, args):
        return self._run(args, map)

    def run_parallel(self, args):
        import multiprocessing

        job_pool = multiprocessing.Pool(processes=2)

        return self._run(args, job_pool.map)

    def _process_line(self, line):
        try:
            (date_time, rest) = line.split("|", 1)

            date_time = datetime.strptime(date_time, "%Y/%m/%d %H:%M:%S.%f")

            (kind, d_or_e, nid, localtime, details) = rest.split(":", 4)
 
            return (date_time, kind, d_or_e, int(nid), int(localtime), details)

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

        return result

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
        results = analyse.run_parallel(args)

    pickle_path = os.path.join(args.results_dir, "results.pickle")

    print("Saving results to", pickle_path)

    with open(pickle_path, 'wb') as pickle_file:
        pickle.dump(results, pickle_file, protocol=pickle.HIGHEST_PROTOCOL)

    print("Results saved")

if __name__ == "__main__":
    main()
