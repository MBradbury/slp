#!/bin/bash

USER=$1
SITE=$2
TESTID=$3

BASE_DIR="testbed_results/fitiotlab"

mkdir -p "$BASE_DIR"

# Now to get some of the other files back from the testbed
rsync -avz --prune-empty-dirs $USER@$SITE:~/.iot-lab/$TESTID/ $BASE_DIR/$TESTID/

if [ ! -d "$BASE_DIR/$TESTID" ]
then
    echo "The directory $BASE_DIR/$TESTID does not exist"
    exit 1
fi

cd "$BASE_DIR/$TESTID"

gunzip aggregator_log.stderr.gz
gunzip aggregator_log.stdout.gz

cd - > /dev/null

experiment-cli get -i $TESTID -p > $BASE_DIR/$TESTID/experiment.json

name=$(jq -r '.name' $BASE_DIR/$TESTID/experiment.json)

new_name=$(echo "${name}_$TESTID" | sed '0,/-/s//\//')

DIRNAME=$(dirname $new_name)

mkdir -p "$BASE_DIR/$DIRNAME"

mv "$BASE_DIR/$TESTID" "$BASE_DIR/${new_name}"

echo "Saved IoT Lab results to $BASE_DIR/${new_name}"
