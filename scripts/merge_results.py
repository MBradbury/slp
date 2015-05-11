#!/usr/bin/env python

from __future__ import print_function

import os, sys, fnmatch

class MergeResults:
    def __init__(self, results_dir, merge_dir):
        self.results_dir = results_dir
        self.merge_dir = merge_dir

    _arguments_to_ignore = {'job_size'}

    @staticmethod
    def _read_arguments(f):
        arguments = {}

        for line in f:
            if '=' in line:
                # We are reading the options so record them
                opt = line.split('=')

                if opt[0] not in MergeResults._arguments_to_ignore:
                    arguments[opt[0]] = opt[1]

            elif line.startswith('#'):
                break

        if len(arguments) == 0:
            raise RuntimeError("There are no arguments")

        return arguments

    @staticmethod
    def _match_arguments(a, b):
        if a.keys() != b.keys():
            raise RuntimeError("Keys of parameters do not match ({}, {})".format(a.keys(), b.keys()))

        shared_items = set(a.items()) & set(b.items())

        if len(shared_items) != len(a) or len(shared_items) != len(b):

            unshared_items = set(a.items()) ^ set(b.items())

            raise RuntimeError("Values do not match ({})".format(unshared_items))

    @staticmethod
    def _write_merged_results(in1, in2, out):
        for line in in1:
            out.write(line)

        seen_hash = False

        for line in in2:
            if line.startswith('#'):
                seen_hash = True
            else:
                if seen_hash:
                    out.write(line)


    def merge_files(self, result_file):
        result_path = os.path.join(self.results_dir, result_file)
        other_path = os.path.join(self.merge_dir, result_file)

        merge_path = os.path.join(self.results_dir, result_file + ".merge")
        backup_path = os.path.join(self.results_dir, result_file + ".backup")

        print("Merging {}".format(result_file))

        with open(result_path, 'r') as out_file, \
             open(other_path, 'r') as in_file:

            result_args = self._read_arguments(out_file)
            merge_args = self._read_arguments(in_file)

            self._match_arguments(result_args, merge_args)

            # Return to start of file
            out_file.seek(0)
            in_file.seek(0)

            print("Creating and writing {}".format(merge_path))

            with open(merge_path, 'w+') as merged_file:
                self._write_merged_results(out_file, in_file, merged_file)

        os.rename(result_path, backup_path)
        os.rename(merge_path, result_path)


def main():
    results_dir = sys.argv[1]
    to_merge_with_dir = sys.argv[2]

    merge = MergeResults(results_dir, to_merge_with_dir)

    for result_file in os.listdir(results_dir):
        if fnmatch.fnmatch(result_file, '*.txt'):
            try:
                merge.merge_files(result_file)
            except (RuntimeError, IOError) as ex:
                print("Failed to merge files due to {}".format(ex))

            print("")

if __name__ == '__main__':
    main()
