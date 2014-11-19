#!/bin/bash
python scripts/my-qstat.py | grep R | cut -d' ' -f 3 | tr . / | awk '{print $0 ".txt"}' | xargs wc -l
