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

curl --user $USER:$PASSWORD $SERVER_URL/webdav/$TESTID/results.tar.gz --output results.$TESTID.tar.gz
