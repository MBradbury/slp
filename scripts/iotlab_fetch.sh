#!/bin/bash

USER=$1
SITE=$2
TESTID=$3

mkdir -p testbed_results/iotlab

#experiment-cli get -i $TESTID -a

#mv $TESTID.tar.gz testbed_results/iotlab/results.$TESTID.tar.gz

#if [ ! -f "./testbed_results/iotlab/results.$TESTID.tar.gz" ]
#then
#	echo "Failed to fetch file"
#	exit 1
#fi

#tar xzf testbed_results/iotlab/results.$TESTID.tar.gz --directory testbed_results/iotlab

#rm testbed_results/iotlab/results.$TESTID.tar.gz

# Remove submitted binaries
#rm testbed_results/iotlab/$TESTID/*.ihex

# Now to get some of the other files back from the testbed
rsync -avz $USER@$SITE:~/.iot-lab/$TESTID/ testbed_results/iotlab/$TESTID/

cd testbed_results/iotlab/$TESTID/

gunzip aggregator_log.stderr.gz

cd -

echo "Saved IoT Lab results to testbed_results/iotlab/$TESTID"
