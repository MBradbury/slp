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

mkdir -p "testbed_results/flocklab"
rm -f "testbed_results/flocklab/testconfiguration.xml"

echo "Downloading ${TESTID} configuration..."

curl -s -S -w "%{http_code}" --user $USER:$PASSWORD $SERVER_URL/webdav/$TESTID/testconfiguration.xml --output testbed_results/flocklab/testconfiguration.xml

if [ ! -f "testbed_results/flocklab/testconfiguration.xml" ]
then
    echo ": Failed to fetch file for $TESTID/testconfiguration.xml"
    exit 1
fi

echo ": Processing results..."

NAME=$(cat testbed_results/flocklab/testconfiguration.xml | sed 's/xmlns=".*"//g' | xmllint --xpath '/testConf/generalConf/description/text()' - )
DIRNAME=$(dirname $NAME)
SAVEPATH="testbed_results/flocklab/${NAME}_$TESTID"

if [ -d "$SAVEPATH" ]
then
    rm -f "testbed_results/flocklab/testconfiguration.xml"
    echo "Already have results for $TESTID, so skipping it."
    exit 2
fi

echo "Downloading results for ${TESTID}..."

curl -s -S -w "%{http_code}" --user $USER:$PASSWORD $SERVER_URL/webdav/$TESTID/results.tar.gz --output testbed_results/flocklab/results.$TESTID.tar.gz

if [ ! -f "./testbed_results/flocklab/results.$TESTID.tar.gz" ]
then
    rm -f "testbed_results/flocklab/testconfiguration.xml"
	echo ": Failed to fetch file for $TESTID"
	exit 1
fi

echo ": Extracting results..."

tar xzf testbed_results/flocklab/results.$TESTID.tar.gz --directory testbed_results/flocklab

echo "Zipping power profiling..."

# Compress the power profile, it tends to be very large!
cd testbed_results/flocklab/$TESTID
gzip --best powerprofiling.csv
cd  - > /dev/null

rm testbed_results/flocklab/results.$TESTID.tar.gz

mv testbed_results/flocklab/testconfiguration.xml testbed_results/flocklab/$TESTID/testconfiguration.xml

mkdir -p "testbed_results/flocklab/$DIRNAME"

mv "testbed_results/flocklab/$TESTID" "$SAVEPATH"

echo "Saved FlockLab results $TESTID to $SAVEPATH"
