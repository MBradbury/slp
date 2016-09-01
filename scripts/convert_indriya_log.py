#!/usr/bin/env python
from __future__ import print_function, division

import csv
import glob
import os

import pandas

# The node types. See algorithm/common/SerialMetricLoggingTypes.h for the definition
AM_METRIC_RECEIVE_MSG = 50
AM_METRIC_BCAST_MSG = 51
AM_METRIC_DELIVER_MSG = 52
AM_ATTACKER_RECEIVE_MSG = 53
AM_METRIC_NODE_CHANGE_MSG = 54
AM_ERROR_OCCURRED_MSG = 54

def catter_header(row, d_or_e, channel):
    # For the local time, we could use "local_time" which is the node local time.
    # However, using "milli_time" is easier

    return "{}:{}:{}:{}:".format(channel, d_or_e, row["node_id"], row["milli_time"])

def catter_metric_receive_msg(row, channel):
    return catter_header(row, "D", channel) + "RCV:{},{},{},{},{}".format(
        row["message_type"], row["proximate_source"], row["ultimate_source"], row["sequence_number"], row["distance"]
    )

def catter_metric_bcast_msg(row, channel):
    return catter_header(row, "D", channel) + "BCAST:{},{},{}".format(
        row["message_type"], row["status"], row["sequence_number"]
    )

def catter_metric_deliver_msg(row, channel):
    return catter_header(row, "D", channel) + "DELIV:{},{},{},{}".format(
        row["message_type"], row["proximate_source"], row["ultimate_source_poss_bottom"], row["sequence_number"]
    )

def catter_attacker_receive_msg(row, channel):
    return catter_header(row, "D", channel) + "{},{},{},{}".format(
        row["message_type"], row["proximate_source"], row["ultimate_source_poss_bottom"], row["sequence_number"]
    )

def catter_metric_node_change_msg(row, channel):
    return catter_header(row, "D", channel) + "{},{}".format(
        row["old_message_type"], row["new_message_type"]
    )

def catter_error_occurred_msg(row, channel):
    return catter_header(row, "E", channel) + "{}".format(
        row["error_code"]
    )

def default_catter(row, channel):
    return catter_header(row, "F", channel)

message_types_to_channels = {
    AM_METRIC_RECEIVE_MSG: ("M-C", catter_metric_receive_msg),
    AM_METRIC_BCAST_MSG: ("M-C", catter_metric_bcast_msg),
    AM_METRIC_DELIVER_MSG: ("M-C", catter_metric_deliver_msg),
    AM_ATTACKER_RECEIVE_MSG: ("A-R", catter_attacker_receive_msg),
    AM_METRIC_NODE_CHANGE_MSG: ("M-NC", catter_metric_node_change_msg),
    AM_ERROR_OCCURRED_MSG: ("stderr", catter_error_occurred_msg),
}

def _read_dat_file(path):
    try:
        reader = pandas.read_csv(path, delimiter="\t", parse_dates=True)

        # Check there is only one message type
        if len(reader["type"].unique()) != 1:
            raise RuntimeError("The type column has more than 1 value.")

        message_type = reader["type"][0]

        # Don't need the type column any more
        del reader["type"]

        reader["milli_time"] -= reader["milli_time"][0]

        return (message_type, reader)
    except pandas.io.common.EmptyDataError:
        # Skip empty files
        return (None, None)

def convert_indriya_log(directory, output_file_path):

    dat_file_paths = glob.glob(os.path.join(directory, "*.dat"))

    dat_files = {message_type: reader
                 for (message_type, reader)
                 in (_read_dat_file(path) for path in dat_file_paths)
                 if message_type is not None
    }

    dfs = []

    for (message_type, dat_file) in dat_files.items():
        channel, fn = message_types_to_channels[message_type]

        df = pandas.DataFrame({
            "line": dat_file.apply(fn, axis=1, args=(channel,)),
            "time": dat_file["milli_time"]
        })

        dfs.append(df)

    cdf = pandas.concat(dfs).sort_values(by="time")

    del cdf["time"]

    with open(output_file_path, 'w') as output_file:
        for line in cdf["line"]:
            print(line, file=output_file)

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Indriya Result Converter", add_help=True)
    parser.add_argument("--result-dir", type=str, required=True, help="The location of the main results files.")
    parser.add_argument("--output-file", type=str, required=True, help="The location of the merged result file.")

    args = parser.parse_args(sys.argv[1:])
    
    convert_indriya_log(args.result_dir, args.output_file)
