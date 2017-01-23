#!/bin/bash

set -x

fullfile=$1

directory=$(dirname "$fullfile")
filename=$(basename "$fullfile")
extension="${filename##*.}"
filename_without_ext="${filename%.*}"

cd "$directory"

rm -rf "$filename_without_ext.so" "$filename_without_ext.c"

#cython -X boundscheck=False -X wraparound=False -X nonecheck=False -X cdivision=True "$filename"
cython "$filename"

gcc -shared -pthread -fPIC -fwrapv -O2 -Wall -fno-strict-aliasing $(python-config --includes) -o "$filename_without_ext.so" "$filename_without_ext.c"

rm -f "$filename_without_ext.pyo" "$filename_without_ext.pyc"

cd -
