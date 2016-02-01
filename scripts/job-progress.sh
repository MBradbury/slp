#!/bin/bash
python scripts/${1}-qstat.py ${@:2} | grep R | column -t | tr -s ' ' | cut -d' ' -f 3 | tr . / | awk '{print $0 ".txt"}' | xargs wc -l
