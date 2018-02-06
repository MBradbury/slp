#!/usr/bin/env python3
import fnmatch
import os

class MergeResults:

    _arguments_to_ignore = {'job_size', 'thread_count', 'verbose', 'job_id'}

    def __init__(self, results_dir, merge_dir):
        self.results_dir = results_dir
        self.merge_dir = merge_dir

    @classmethod
    def _read_arguments(cls, f):
        arguments = {}

        for line in f:

            # Skip meta data
            if line[0] == '@':
                continue

            # We are reading the options so record them
            elif '=' in line:
                opt = line.split('=', 1)

                if opt[0] not in cls._arguments_to_ignore:
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

        hash_line1 = None

        for line in in1:
            if line.startswith('#'):
                hash_line1 = line

            out.write(line)

        hash_line2 = None

        for line in in2:
            if line.startswith('#'):
                hash_line2 = line

                if hash_line2 != hash_line1:
                    raise RuntimeError("The result names do not match {} / {}".format(hash_line1, hash_line2))

            else:
                if hash_line2 is not None or line[0] == '@':
                    out.write(line)

    def merge_files(self, result_file):
        result_path = os.path.join(self.results_dir, result_file)
        other_path = os.path.join(self.merge_dir, result_file)

        merge_path = os.path.join(self.results_dir, result_file + ".merge")
        backup_path = os.path.join(self.results_dir, result_file + ".backup")

        with open(result_path, 'r') as out_file, \
             open(other_path, 'r') as in_file:

            result_args = self._read_arguments(out_file)
            merge_args = self._read_arguments(in_file)

            self._match_arguments(result_args, merge_args)

            # Return to start of file
            out_file.seek(0)
            in_file.seek(0)

            print("Merging '{}' with '{}'".format(result_path, other_path))
            print("Creating and writing {}".format(merge_path))

            with open(merge_path, 'w+') as merged_file:
                self._write_merged_results(out_file, in_file, merged_file)

        os.rename(result_path, backup_path)
        os.rename(merge_path, result_path)

        os.rename(other_path, other_path + ".processed")


def main(results_dir, to_merge_with_dir):
    merge = MergeResults(results_dir, to_merge_with_dir)

    failures = []

    for result_file in os.listdir(results_dir):
        if fnmatch.fnmatch(result_file, '*.txt'):
            try:
                merge.merge_files(result_file)
                print("")
            except (RuntimeError, IOError) as ex:
                failures.append("Failed to merge files due to {}".format(ex))

    for failure in failures:
        print(failure)

if __name__ == '__main__':
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Result Merger", add_help=True)
    parser.add_argument("--result-dir", type=str, required=True, help="The location of the main results files. The merged results will be stored here.")
    parser.add_argument("--merge-dir", type=str, required=True, help="The location of the results to merge.")

    args = parser.parse_args(sys.argv[1:])

    main(args.result_dir, args.merge_dir)
