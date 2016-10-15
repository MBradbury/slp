#!/bin/bash

cd data/

rm -rf analysis.so analysis.c

cython analysis.py

gcc -shared -pthread -fPIC -fwrapv -O2 -Wall -fno-strict-aliasing $(python-config --includes) -o analysis.so analysis.c

rm -f analysis.pyo analysis.pyc

cd -
