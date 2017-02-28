#!/usr/bin/env python
from __future__ import print_function, division

from datetime import datetime
import re

def _incremental_ave(curr, item, count):
	return curr + (item - curr) / (count + 1), count + 1

def convert_avrora_log(result_file, output_file):

	results_start = "------------------------------------------------------------------------------"
	results_end = "=============================================================================="

	RESULT_LINE_RE = re.compile(r'\s*(\d+)\s*(\d+:\d+:\d+\.\d+)\s*(.+)\s*')
	TX_LINE_RE = re.compile(r'---->\s+((?:[0-9A-F][0-9A-F]\.)*[0-9A-F][0-9A-F])\s+(\d+\.\d+)\s+ms\s*')
	RX_LINE_RE = re.compile(r'<====\s+((?:[0-9A-F][0-9A-F]\.)*[0-9A-F][0-9A-F])\s+(\d+\.\d+)\s+ms\s*')

	started = False
	ended = False

	average_tx_length = 0
	average_rx_length = 0

	average_tx_count = 0
	average_rx_count = 0

	with open(result_file, 'r') as result, open(output_file, 'w') as output:

		for line in result:
			if not started and line.startswith(results_start):
				started = True
				print("started")
				continue

			if not started:
				continue

			if line.startswith(results_end):
				ended = True
				print("ended")
				continue

			if started and not ended:
				match = RESULT_LINE_RE.match(line)

				node = int(match.group(1))
				node_time = datetime.strptime(match.group(2)[:-3], "%H:%M:%S.%f")

				log = match.group(3)

				if log.startswith("---->"):
					tx_match = TX_LINE_RE.match(log)
					data = tx_match.group(1)
					time_length_ms = float(tx_match.group(2))

					average_tx_length, average_tx_count = _incremental_ave(average_tx_length, time_length_ms, average_tx_count)

				elif log.startswith("<===="):
					rx_match = RX_LINE_RE.match(log)
					data = rx_match.group(1)
					time_length_ms = float(rx_match.group(2))

					average_rx_length, average_rx_count = _incremental_ave(average_rx_length, time_length_ms, average_rx_count)

				else:
					dtime_str = node_time.strftime("%Y/%m/%d %H:%M:%S.%f")

					# Then its one of our debug log messages
					print(dtime_str + "|" + log, file=output)

	print("Average Tx:", average_tx_length, "ms")
	print("Average Rx:", average_rx_length, "ms")
	print("Count Tx:", average_tx_count)
	print("Count Rx:", average_rx_count)

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Avrora Result Converter", add_help=True)
    parser.add_argument("-in", "--result-file", type=str, required=True, help="The location of the result file.")
    parser.add_argument("-out", "--output-file", type=str, required=True, help="The location of the converted result file.")

    args = parser.parse_args(sys.argv[1:])
    
    convert_avrora_log(args.result_file, args.output_file)

