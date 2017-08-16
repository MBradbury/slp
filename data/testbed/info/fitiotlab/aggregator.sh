#!/bin/bash

#if [ "$#" -eq 1 ]
#	then
#	echo "Source script config path: $1" >&2
#	source $1
#	auth-cli -u ${IOTUSER} -p ${IOTPASSWORD}
#fi

# Redirect all nodes serial output to a file
readonly OUTFILE="${HOME}/.iot-lab/${EXP_ID}/aggregator_log.stdout"
readonly ERRFILE="${HOME}/.iot-lab/${EXP_ID}/aggregator_log.stderr"

experiment-cli wait -i ${EXP_ID}

echo "Launch serial_aggregator with exp_id: ${EXP_ID}" >&2
serial_aggregator -i ${EXP_ID} 2> ${ERRFILE} 1> ${OUTFILE}
