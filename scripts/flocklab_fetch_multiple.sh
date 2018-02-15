#!/bin/bash
from=$1
to=$2

echo "Fetching results from $from to $to"

for (( i=$from; i<=$to; i++ ))
do
    ./scripts/flocklab_fetch.sh $i
done
