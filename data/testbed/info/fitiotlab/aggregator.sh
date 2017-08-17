#!/bin/bash

trap 'catch_signal; exit' SIGTERM

catch_signal()
{
	echo "Catch SIGTERM signal" >&2
	#if [ "$#" -eq 1 ]
	#then
	#	echo "Source script config path: $1" >&2
	#	source $1
	#fi
	gzip -9 ${OUTFILE}
	gzip -9 ${ERRFILE}

	mv ${OUTFILE}.gz ${OUTFILE}_$(hostname)_${EXP_ID}.gz
	mv ${ERRFILE}.gz ${ERRFILE}_$(hostname)_${EXP_ID}.gz
}

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

# Reset all nodes, so they boot at the same time
node-cli -i ${EXP_ID} --reset

echo "Launch serial_aggregator with exp_id: ${EXP_ID}" >&2
serial_aggregator -i ${EXP_ID} 2> ${ERRFILE} 1> ${OUTFILE}
