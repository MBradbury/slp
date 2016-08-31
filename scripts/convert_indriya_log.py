#!/usr/bin/env python
from __future__ import print_function, division

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

message_types_to_channels = {
    AM_METRIC_RECEIVE_MSG: "M-C",
    AM_METRIC_BCAST_MSG: "M-C",
    AM_METRIC_DELIVER_MSG: "M-C",
    AM_ATTACKER_RECEIVE_MSG: "A-R",
    AM_METRIC_NODE_CHANGE_MSG: "M-NC",
    AM_ERROR_OCCURRED_MSG: "stderr",
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

        #reader["milli_time"] -= reader["milli_time"][0]

        return (message_type, reader)
    except pandas.io.common.EmptyDataError:
        # Skip empty files
        return (None, None)

def convert_indriya_log(directory, output_file):

    dat_file_paths = glob.glob(os.path.join(directory, "*.dat"))

    dat_files = {message_type: reader
                 for (message_type, reader)
                 in (_read_dat_file(path) for path in dat_file_paths)
                 if message_type is not None
    }

    print(dat_files)

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Indriya Result Converter", add_help=True)
    parser.add_argument("--result-dir", type=str, required=True, help="The location of the main results files.")
    parser.add_argument("--output-file", type=str, required=True, help="The location of the merged result file.")

    args = parser.parse_args(sys.argv[1:])
    
    convert_indriya_log(args.result_dir, args.output_file)
