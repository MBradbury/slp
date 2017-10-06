#!/bin/bash

USER=$1
SITE=$2
TESTID=$3

mkdir -p testbed_results/iotlab

# Now to get some of the other files back from the testbed
rsync -avz --prune-empty-dirs $USER@$SITE:~/.iot-lab/$TESTID/ testbed_results/iotlab/$TESTID/

if [ ! -d "testbed_results/iotlab/$TESTID" ]
then
    echo "The directory testbed_results/iotlab/$TESTID does not exist"
    exit 1
fi

cd "testbed_results/iotlab/$TESTID"

gunzip aggregator_log.stderr.gz
gunzip aggregator_log.stdout.gz

cd - > /dev/null

experiment-cli get -i $TESTID -p > testbed_results/iotlab/$TESTID/experiment.json

name=$(jq -r '.name' testbed_results/iotlab/$TESTID/experiment.json)

new_name=$(echo "${name}_$TESTID" | sed '0,/-/s//\//')

DIRNAME=$(dirname $new_name)

mkdir -p "testbed_results/iotlab/$DIRNAME"

mv "testbed_results/iotlab/$TESTID" "testbed_results/iotlab/${new_name}"

echo "Saved IoT Lab results to testbed_results/iotlab/${new_name}"
