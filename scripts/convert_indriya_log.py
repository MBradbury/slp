#!/usr/bin/env python
from __future__ import print_function, division

from simulator.OfflineLogConverter import Indriya as IndriyaLogConverter

def convert_indriya_log(result_dir, output_path):

    converter = IndriyaLogConverter(result_dir)

    with open(output_path, 'w') as output_file:
        for line in converter:
            print(line, file=output_file)

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Indriya Result Converter", add_help=True)
    parser.add_argument("-in", "--result-dir", type=str, required=True, help="The location of the main results files.")
    parser.add_argument("-out", "--output-file", type=str, required=True, help="The location of the merged result file.")

    args = parser.parse_args(sys.argv[1:])
    
    convert_indriya_log(args.result_dir, args.output_file)
