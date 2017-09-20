#!/bin/bash

for name in *.gp
do
	gnuplot "$name"
done

for name in *.pdf
do
	pdfcrop "$name" "$name"
done
