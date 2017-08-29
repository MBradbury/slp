#!/bin/bash

# Redirect all nodes serial output to a file
readonly OUTFILE="${HOME}/.iot-lab/${EXP_ID}/aggregator_log.stdout"
readonly ERRFILE="${HOME}/.iot-lab/${EXP_ID}/aggregator_log.stderr"

trap 'catch_signal; exit' SIGTERM

catch_signal()
{
	echo "Catch SIGTERM signal" >&2

	SA_PID = $(ps aux | grep serial_aggregator | grep python | tr -s ' ' | cut -f 2 -d' ')

	echo "Killing serial_aggregator with PID $SA_PID" >&2
	kill $SA_PID

	sleep 1

	gzip -9 ${OUTFILE}
	gzip -9 ${ERRFILE}
}

echo "serial_aggregator -v" >&2
serial_aggregator -v >&2

experiment-cli wait -i ${EXP_ID}

# Reset all nodes, so they boot at the same time
node-cli -i ${EXP_ID} --reset

echo "Launch serial_aggregator with exp_id: ${EXP_ID}" >&2
serial_aggregator -i ${EXP_ID} 2> ${ERRFILE} 1> ${OUTFILE}
