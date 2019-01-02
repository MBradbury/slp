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
        super(UnknownTestbedError, self).__init__(f"Unknown testbed {testbed}")


class TimeResult(object):
    def __init__(self):
        self.initial_global = None
        self.initial_local = None

        self.times_global = []
        self.times_local = []

    def add(self, date_time, kind, d_or_e, nid, localtime, details):
        # Convert both to seconds
        if localtime is not None and localtime != "None":
            g, l = date_time.timestamp(), int(localtime) / 1000.0
        else:
            g, l = date_time.timestamp(), float('NaN')

        if self.initial_global is None:
            self.initial_global = g
        if self.initial_local is None:
            self.initial_local = l

        self.times_global.append(g - self.initial_global)
        self.times_local.append(l - self.initial_local)

    def combine(self, other):
        raise RuntimeError("Doesn't make sense?")

        """result = TimeResult()

        result.times.extend(self.times)
        result.times.extend(other.times)

        return result"""


class RSSIResult(object):
    def __init__(self):
        self.node_average = {}
        self.node_smallest = {}
        #self.node_largest = {}

        self.total_reads = {}

        #self.start_time = None
        #self.stop_time = None

    def add(self, date_time, kind, d_or_e, nid, localtime, details):
        if kind == "M-RSSI":
            (average, smallest, largest, reads, channel) = map(int, details.split(",", 4))

            key = (nid, channel)

            average = _adjust_tinyos_raw_rssi(average)
            smallest = _adjust_tinyos_raw_rssi(smallest)
            #largest = _adjust_tinyos_raw_rssi(largest)

            if key not in self.node_average:
                self.node_average[key] = RunningStats()
                self.node_smallest[key] = smallest
                self.total_reads[key] = 0

            self.node_average[key].push(average)
            self.node_smallest[key] = min(self.node_smallest[key], smallest)
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
            try:
                self_ave, self_smallest, self_total = self.node_average[key], self.node_smallest[key], self.total_reads[key]
            except KeyError:
                self_ave, self_smallest, self_total = RunningStats(), None, 0

            try:
                other_ave, other_smallest, other_total = other.node_average[key], other.node_smallest[key], other.total_reads[key]
            except KeyError:
                other_ave, other_smallest, other_total = RunningStats(), None, 0

            result.node_average[key] = self_ave.combine(other_ave)
            result.node_smallest[key] = min(x for x in (self_smallest, other_smallest) if x is not None)
            #result.node_largest[key] = self.node_largest[key].combine(other.node_largest[key])

            result.total_reads[key] = self_total + other_total

        #result.start_time = min(self.start_time, other.start_time)
        #result.stop_time = max(self.stop_time, other.stop_time)

        return result


class LinkResult(object):
    def __init__(self, channel):
        self.broadcasting_node_id = None
        self.broadcasts = 0
        self.broadcast_power = None
        self.channel = int(channel)

        self.deliver_at_rssi = defaultdict(RunningStats)
        self.deliver_at_lqi = defaultdict(RunningStats)

    def add(self, date_time, kind, d_or_e, nid, localtime, details):
        if kind == "M-CB":
            (msg_type, status, ultimate_src, seq_no, tx_power, payload) = details.split(",", 5)

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
            (msg_type, target, proximate_src, ultimate_src, seq_no, rssi, lqi, payload) = details.split(",", 7)

            rssi = _adjust_tinyos_rssi(int(rssi))
            lqi = int(lqi)

            #print("Deliv ", seq_no, " rssi ", rssi, " lqi ", lqi)

            self.deliver_at_rssi[nid].push(rssi)
            self.deliver_at_lqi[nid].push(lqi)

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
        if self.channel != other.channel:
            raise RuntimeError("Bad channel")

        result = LinkResult(self.channel)

        result.broadcasting_node_id = self.broadcasting_node_id
        result.broadcast_power = self.broadcast_power

        result.broadcasts = self.broadcasts + other.broadcasts

        for nid in set(self.deliver_at_rssi.keys()) | set(other.deliver_at_rssi.keys()):
            result.deliver_at_rssi[nid] = self.deliver_at_rssi[nid].combine(other.deliver_at_rssi[nid])
            result.deliver_at_lqi[nid] = self.deliver_at_lqi[nid].combine(other.deliver_at_lqi[nid])

        return result


class CurrentDraw(object):
    def __init__(self, summary_df, bad_df=None,
                 broadcasting_node_id=None, broadcast_power=None, channel=None):

        self.summary_df = summary_df
        self.bad_df = bad_df

        self.broadcasting_node_id = broadcasting_node_id
        self.broadcast_power = broadcast_power
        self.channel = channel


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
        if input_string == "\0":
            return "NUL"
        else:
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

        if isinstance(result, RSSIResult):
            with open(results_dir + "_rssi.txt", "w") as rssi_log_file:
                self._create_noise_log(converter, rssi_log_file)

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

    def _get_average_current_draw(self, results_dir, measurement_results, **kwargs):

        pickle_path = os.path.join(results_dir, "current.pickle")

        if os.path.exists(pickle_path) and not self.flush:
            print("Loading saved current results from:", pickle_path)
            try:
                with open(pickle_path, 'rb') as pickle_file:
                    return pickle.load(pickle_file)
            except EOFError:
                print("Failed to load saved current results from:", pickle_path)

        print("Reading raw current results")

        if self.testbed_name == "flocklab":

            raw_df = measurement_results["powerprofiling.csv"]
            raw_df.rename(columns={"node_id": "node", "value_mA": "I"}, inplace=True)

            df = raw_df.groupby("node")["I"].agg([np.mean, var0, len]).reset_index()

            result = CurrentDraw(df, **kwargs)

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

            result = CurrentDraw(df, bad_df=removed_df, **kwargs)

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
            print(f"Unable to read results from {results_dir} as is not not a directory")
            return None

        result = self._parse_aggregation(results_dir)
        #if result is None:
        #    return None
        
        measurement_results = self._parse_measurements(results_dir)

        try:
            average_current_draw = self._get_average_current_draw(results_dir, measurement_results,
                broadcasting_node_id=getattr(result, "broadcasting_node_id", None),
                broadcast_power=getattr(result, "broadcast_power", None),
                channel=getattr(result, "channel", None)
            )

        except (UnknownTestbedError, KeyError) as ex:
            print(ex)
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

        return result, average_current_draw#, time_result #, rssi_extra

    def _run(self, args, map_fn):
        files = [
            os.path.join(args.results_dir, result_folder)
            for result_folder
            in os.listdir(args.results_dir)
            if os.path.isdir(os.path.join(args.results_dir, result_folder))
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
            (date_time, rest) = line
            (kind, d_or_e, nid, localtime, details) = rest.split(":", 4)

            localtime == None if localtime == "None" else int(localtime)
 
            return (date_time, kind, d_or_e, int(nid), localtime, details)

        except BaseException as ex:
            try:
                sanitised_string = self._sanitise_string(line)
                sanitised_ex = self._sanitise_string(str(ex))
            except BaseException as ex2:
                print(f"Failed to sanitise the string due to {ex2}", file=sys.stderr)
                traceback.print_exc()
                sanitised_string = None
                sanitised_ex = None

            print(f"Failed to parse the line: {sanitised_string} with {sanitised_ex}", file=sys.stderr)
            traceback.print_exc()

            return None

    def _get_channel_from_filename(self, converter):
        dirname = os.path.basename(os.path.dirname(converter.log_path))
        # E.g., FlockLabSource10Sink1-31-26-disabled-0_5_62394
        configuration, tx_power, channel, lpl, psrc_and_run = dirname.split('-')
        assert int(channel) in range(11, 27)
        return int(channel)

    """def _cheeky_plot(self, time_result):
        import matplotlib.pyplot as plt

        plt.plot(time_result.times_global, time_result.times_local)

        plt.show()"""

    def _analyse_log_file(self, converter):
        result = None
        #time_result = TimeResult()

        for line in converter:

            line_result = self._process_line(line)
            if line_result is None:
                continue

            if result is None:
                kind, details = line_result[1], line_result[5]
                if kind == "stdout" and "An object has been detected" in details:
                    ch = self._get_channel_from_filename(converter)
                    result = LinkResult(ch)

                elif kind == "M-RSSI":
                    result = RSSIResult()

                else:
                    continue

            try:
                result.add(*line_result)
                #time_result.add(*line_result)
            except ValueError as ex:
                print("Failed to parse: ", self._sanitise_string(line))
                traceback.print_exc()

        #self._cheeky_plot(time_result)

        return result#, time_result

    def _create_noise_log(self, converter, rssi_log_file):
        result = None

        for line in converter:

            line_result = self._process_line(line)
            if line_result is None:
                continue

            (date_time, kind, d_or_e, nid, localtime, details) = line_result

            if kind != "M-RSSI":
                continue

            (average, smallest, largest, reads, channel) = details.split(",", 4)

            average = _adjust_tinyos_raw_rssi(int(average))

            print_line = ",".join((str(nid), str(average)))

            print(print_line, file=rssi_log_file)

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
