#!/usr/bin/env python
from __future__ import print_function

import simulator.OfflineLogConverter as ConverterModule

def convert_log(class_name, result_file, output_path):

    Converter = getattr(ConverterModule, class_name)

    converter = Converter(result_file)

    with open(output_path, 'w') as output_file:
        for line in converter:
            print(line, file=output_file)

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Result Converter", add_help=True)
    parser.add_argument("name", type=str, help="The name of the converter clss")
    parser.add_argument("-in", "--result-file", type=str, required=True, help="The location of the result file.")
    parser.add_argument("-out", "--output-file", type=str, required=True, help="The location of the converted result file.")

    args = parser.parse_args(sys.argv[1:])
    
    convert_log(args.name, args.result_file, args.output_file)
