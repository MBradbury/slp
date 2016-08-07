#!/usr/bin/env python

from __future__ import print_function

import csv
import sys

if __name__ == "__main__":
    
    filename = sys.argv[1]

    with open(filename, 'r') as f:
        reader = csv.reader(f, delimiter='\t')

        for line in reader:
            (data_line, date, nid, time_ms, no) = line

            # TODO: use time_ms to create the time

            # Skip first line
            if no == "motelabSeqNo":
                continue

            data_line = data_line.replace("\\0", "")
            nid = int(nid)

            # The first line needs a date and time too
            if no == "1":
                data_line = date + ":" + data_line

            print(data_line.replace("\\n", "\n{}:".format(date)), end='')
