#!/bin/bash

TESTID=$1

SERVER_URL=https://www.flocklab.ethz.ch/user
CURL_PARAMS=-s
if [ -f .flocklabauth ]
then
  source ./.flocklabauth
else
  if [ -f $HOME/.flocklabauth ]
  then
    source $HOME/.flocklabauth
  fi
fi

mkdir -p testbed_results/flocklab

echo "Downloading results for ${TESTID}..."

curl -s -S --user $USER:$PASSWORD $SERVER_URL/webdav/$TESTID/results.tar.gz --output testbed_results/flocklab/results.$TESTID.tar.gz

if [ ! -f "./testbed_results/flocklab/results.$TESTID.tar.gz" ]
then
	echo "Failed to fetch file for $TESTID"
	exit 1
fi

echo "Extracting results..."

tar xzf testbed_results/flocklab/results.$TESTID.tar.gz --directory testbed_results/flocklab

echo "Zipping power profiling..."

# Compress the power profile, it tends to be very large!
cd testbed_results/flocklab/$TESTID
gzip --best powerprofiling.csv
cd  - > /dev/null

rm testbed_results/flocklab/results.$TESTID.tar.gz

echo "Downloading configuration..."

curl -s --user $USER:$PASSWORD $SERVER_URL/webdav/$TESTID/testconfiguration.xml --output testbed_results/flocklab/$TESTID/testconfiguration.xml

NAME=$(cat testbed_results/flocklab/$TESTID/testconfiguration.xml | sed 's/xmlns=".*"//g' | xmllint --xpath '/testConf/generalConf/description/text()' - )

DIRNAME=$(dirname $NAME)

mkdir -p "testbed_results/flocklab/$DIRNAME"

mv "testbed_results/flocklab/$TESTID" "testbed_results/flocklab/${NAME}_$TESTID"

echo "Saved FlockLab results $TESTID to testbed_results/flocklab/${NAME}_$TESTID"
