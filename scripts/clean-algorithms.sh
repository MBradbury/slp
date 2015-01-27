#!/bin/bash

for algorithm in algorithm/*
do
	if [[ -d "$algorithm" ]]; then
		echo "$algorithm"
		make clean -C "$algorithm"
		echo
	fi
done
