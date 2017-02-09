#!/bin/bash

files=("topology.txt" "app.c" "ident_flags.txt" "main.elf" "main.ihex" "main.srec" "tos_image.xml" "wiring-check.xml")

for algorithm in algorithm/*
do
	if [[ -d "$algorithm" ]]; then
		echo "$algorithm"
		make clean -C "$algorithm"
		for f in "${files[@]}"
		do
			echo "rm -f \"$algorithm/$f\""
			rm -f "$algorithm/$f" 
		done
		echo
	fi
done
