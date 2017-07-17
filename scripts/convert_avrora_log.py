#!/usr/bin/env python
from __future__ import print_function

from simulator.OfflineLogConverter import Avrora as AvroraLogConverter

def convert_avrora_log(result_file, output_file):

	converter = AvroraLogConverter(result_file)

	for line in converter:
		print(line, file=output_file)

	print("Average Tx:", converter.average_tx_length, "ms")
	print("Average Rx:", converter.average_rx_length, "ms")
	print("Count Tx:", converter.average_tx_count)
	print("Count Rx:", converter.average_rx_count)

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Avrora Result Converter", add_help=True)
    parser.add_argument("-in", "--result-file", type=str, required=True, help="The location of the result file.")
    parser.add_argument("-out", "--output-file", type=str, required=True, help="The location of the converted result file.")

    args = parser.parse_args(sys.argv[1:])
    
    convert_avrora_log(args.result_file, args.output_file)
