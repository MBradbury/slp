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

curl -s --user $USER:$PASSWORD $SERVER_URL/webdav/$TESTID/results.tar.gz --output testbed_results/flocklab/results.$TESTID.tar.gz

tar xzf testbed_results/flocklab/results.$TESTID.tar.gz --directory testbed_results/flocklab

rm testbed_results/flocklab/results.$TESTID.tar.gz

echo "Saved FlockLab results to testbed_results/flocklab/$TESTID"
