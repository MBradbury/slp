#!/bin/bash

JOBID=$1
RESULTID=$2

if [ -f .indriyaauth ]
then
  source ./.indriyaauth
else
  if [ -f $HOME/.indriyaauth ]
  then
    source $HOME/.indriyaauth
  fi
fi


SERVER_URL="https://indriya.comp.nus.edu.sg/users/$USER/jobs/job${JOBID}_${RESULTID}/data-$RESULTID.zip"

mkdir -p testbed_results/indriya/data-$RESULTID

wget --no-check-certificate $SERVER_URL --directory-prefix testbed_results/indriya/
if [ $? -ne 0 ]; then
	echo "wget failed"
	exit 1
fi

unzip testbed_results/indriya/data-$RESULTID.zip -d testbed_results/indriya/data-$RESULTID

rm testbed_results/indriya/data-$RESULTID.zip

echo "Saved Indriya results to testbed_results/indriya/data-$RESULTID"
