#!/usr/bin/python

from __future__ import print_function

import os, sys, fnmatch

results_dir = sys.argv[1]
to_merge_with_dir = sys.argv[2]

def read_arguments(f):
    arguments = {}

    for line in f:
        if '=' in line:
            # We are reading the options so record them
            opt = line.split('=')

            arguments[opt[0]] = opt[1]

        elif line.startswith('#'):
            break

    return arguments

def match_arguments(a, b):
    if a.keys() != b.keys():
        raise RuntimeError("Keys of parameters do not match ({}, {})".format(a.keys(), b.keys()))

    shared_items = set(a.items()) & set(b.items())

    if len(shared_items) != len(a) or len(shared_items) != len(b):
        raise RuntimeError("Values do not match ({}, {})".format(a.items(), b.items()))

def write_merged_results(in1, in2, out):
    for line in in1:
        out.write(line)

    seen_hash = False

    for line in in2:
        if line.startswith('#'):
            seen_hash = True
        else:
            if seen_hash:
                out.write(line)


def merge_files(result_file):
    result_path = os.path.join(results_dir, result_file)
    other_path = os.path.join(to_merge_with_dir, result_file)

    merge_path = os.path.join(results_dir, result_file + ".merge")

    print("Merging {}".format(result_file))

    with open(result_path, 'r') as out_file, \
         open(other_path, 'r') as in_file:

        result_args = read_arguments(out_file)
        merge_args = read_arguments(in_file)

        match_arguments(result_args, merge_args)

        # Return to start of file
        out_file.seek(0)
        in_file.seek(0)

        print("Creating and writing {}".format(merge_path))

        with open(merge_path, 'w+') as merged_file:
            write_merged_results(out_file, in_file, merged_file)

for result_file in os.listdir(results_dir):
    if fnmatch.fnmatch(result_file, '*.txt'):
        try:
            merge_files(result_file)
        except (RuntimeError, IOError) as ex:
            print("Failed to merge files due to {}".format(ex))

        print("")
    