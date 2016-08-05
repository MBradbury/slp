#!/usr/bin/env python
from __future__ import print_function

import pstats
import sys

p = pstats.Stats(sys.argv[1])
p.sort_stats('cumulative').print_stats(50)
