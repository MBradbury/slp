#!/bin/bash

USER=$1
SITE=$2
from=$3
to=$4

if [[ -z $USER ]]; then
    echo "USER not set"
    exit 1
fi
if [[ -z $SITE ]]; then
    echo "SITE not set"
    exit 1
fi
if [[ -z $from ]]; then
    echo "from not set"
    exit 1
fi
if [[ -z $to ]]; then
    echo "to not set"
    exit 1
fi

echo "Fetching results from $from to $to"

for (( i=$from; i<=$to; i++ ))
do
    ./scripts/iotlab_fetch.sh $USER $SITE $i
done
