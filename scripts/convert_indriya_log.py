#!/usr/bin/env python
from __future__ import print_function, division

import glob
import os

import pandas

# The node types. See algorithm/common/SerialMetricLoggingTypes.h for the definition
AM_ERROR_OCCURRED_MSG = 49
AM_METRIC_RECEIVE_MSG = 50
AM_METRIC_BCAST_MSG = 51
AM_METRIC_DELIVER_MSG = 52
AM_ATTACKER_RECEIVE_MSG = 53
AM_METRIC_NODE_CHANGE_MSG = 54
AM_METRIC_NODE_TYPE_ADD_MSG = 55
AM_METRIC_MESSAGE_TYPE_ADD_MSG = 56

def catter_header(row, d_or_e, channel):
    return "{}|{}:{}:{}:{}:".format(row["date_time"], channel, d_or_e, row["node_id"], row["local_time"])

def catter_metric_receive_msg(row, channel):
    return catter_header(row, "D", channel) + "{},{},{},{},{}".format(
        row["message_type"], row["proximate_source"], row["ultimate_source"], row["sequence_number"], row["distance"]
    )

def catter_metric_bcast_msg(row, channel):
    return catter_header(row, "D", channel) + "{},{},{}".format(
        row["message_type"], row["status"], row["sequence_number"]
    )

def catter_metric_deliver_msg(row, channel):
    return catter_header(row, "D", channel) + "{},{},{},{}".format(
        row["message_type"], row["proximate_source"], row["ultimate_source_poss_bottom"], row["sequence_number"]
    )

def catter_attacker_receive_msg(row, channel):
    return catter_header(row, "D", channel) + "{},{},{},{}".format(
        row["message_type"], row["proximate_source"], row["ultimate_source_poss_bottom"], row["sequence_number"]
    )

def catter_metric_node_change_msg(row, channel):
    return catter_header(row, "D", channel) + "{},{}".format(
        row["old_node_type"], row["new_node_type"]
    )

def catter_metric_node_type_add_msg(row, channel):
    return catter_header(row, "D", channel) + "{},{}".format(
        row["node_type_id"], row["node_type_name"]
    )

def catter_metric_message_type_add_msg(row, channel):
    return catter_header(row, "D", channel) + "{},{}".format(
        row["message_type_id"], row["message_type_name"]
    )

def catter_error_occurred_msg(row, channel):
    return catter_header(row, "E", channel) + "{}".format(
        row["error_code"]
    )

def default_catter(row, channel):
    return catter_header(row, "F", channel)

message_types_to_channels = {
    AM_METRIC_RECEIVE_MSG: ("M-CR", catter_metric_receive_msg),
    AM_METRIC_BCAST_MSG: ("M-CB", catter_metric_bcast_msg),
    AM_METRIC_DELIVER_MSG: ("M-CD", catter_metric_deliver_msg),
    AM_ATTACKER_RECEIVE_MSG: ("A-R", catter_attacker_receive_msg),
    AM_METRIC_NODE_CHANGE_MSG: ("M-NC", catter_metric_node_change_msg),
    AM_ERROR_OCCURRED_MSG: ("stderr", catter_error_occurred_msg),
    AM_METRIC_NODE_TYPE_ADD_MSG: ("M-NTA", catter_metric_node_type_add_msg),
    AM_METRIC_MESSAGE_TYPE_ADD_MSG: ("M-MTA", catter_metric_message_type_add_msg),
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

        reader["date_time"] = reader["insert_time"].apply(lambda x: x.replace("-", "/")) + "." + reader["milli_time"].apply(lambda x: str(x % 1000).ljust(3, '0'))

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

    # Remove "\0" from any fields that are strings
    to_remove_nul_char = [(AM_METRIC_NODE_TYPE_ADD_MSG, "node_type_name"), (AM_METRIC_MESSAGE_TYPE_ADD_MSG, "message_type_name")]

    for (ident, name) in to_remove_nul_char:
        dat_files[ident][name] = dat_files[ident][name].apply(lambda x: x.replace("\\0", ""))

    # Find out the numeric to name mappings for message types
    node_types = (
        dat_files[AM_METRIC_NODE_TYPE_ADD_MSG][["node_type_id", "node_type_name"]]
            .drop_duplicates()
            .set_index("node_type_id")
            .to_dict()["node_type_name"]
    )

    # Find out the numeric to name mappings for message types
    message_types = (
        dat_files[AM_METRIC_MESSAGE_TYPE_ADD_MSG][["message_type_id", "message_type_name"]]
            .drop_duplicates()
            .set_index("message_type_id")
            .to_dict()["message_type_name"]
    )

    # Convert any node type ids to node type names
    to_convert_node_type = [(AM_METRIC_NODE_CHANGE_MSG, "old_node_type"), (AM_METRIC_NODE_CHANGE_MSG, "new_node_type")]

    for (ident, name) in to_convert_node_type:
        dat_files[ident][name] = dat_files[ident][name].apply(lambda x: node_types.get(x, "<unknown>"))

    dfs = []

    for (message_type, dat_file) in dat_files.items():
        channel, fn = message_types_to_channels[message_type]

        # Convert numeric message type to string
        if "message_type" in dat_file:
            dat_file["message_type"] = dat_file["message_type"].apply(lambda x: message_types[x])

        # Get the df we want to output
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
    parser.add_argument("-in", "--result-dir", type=str, required=True, help="The location of the main results files.")
    parser.add_argument("-out", "--output-file", type=str, required=True, help="The location of the merged result file.")

    args = parser.parse_args(sys.argv[1:])
    
    convert_indriya_log(args.result_dir, args.output_file)
