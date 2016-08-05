#!/usr/bin/env python

from __future__ import print_function

from collections import defaultdict
import csv
import sys

if __name__ == "__main__":
    
    filename = sys.argv[1]

    data = defaultdict(str)

    with open(filename, 'r') as f:
        reader = csv.reader(f, delimiter='\t')

        for line in reader:
            (data_line, date, nid, time_ms, no) = line

            # Skip first line
            if no == "motelabSeqNo":
                continue

            data_line = data_line.replace("\\0", "")
            nid = int(nid)

            data[nid] += data_line.replace("\\n", "\n{}:".format(date))

    for node_data in data.values():
        print(node_data)
