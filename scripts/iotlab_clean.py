#!/usr/bin/env python
from __future__ import print_function

import os
import sys

directory = sys.argv[1]

contents = list(sorted(os.listdir(directory)))

to_check = ["aggregator_log.stderr", "aggregator_log.stdout", "run_script.log"]

bad_dir = os.path.join(directory, "bad")

for run in contents:

	bad = False
	exists = True

	for path in to_check:
		full_path = os.path.join(directory, run, path)

		exists &= os.path.exists(full_path)

		if not exists:
			break

		bad |= os.path.getsize(full_path) == 0

	if exists:
		if bad:
			print(run, "is bad")

			os.rename(os.path.join(directory, run), os.path.join(directory, "bad", run))