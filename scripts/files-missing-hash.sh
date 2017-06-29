#!/bin/bash
ls *.txt | xargs -l sh -c 'out=$(cat $0 | grep "#" | wc -l); if [ $out -eq 0 ]; then echo $0; fi'
