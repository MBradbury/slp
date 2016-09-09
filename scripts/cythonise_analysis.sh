#!/bin/bash

cd data/

cython analysis.py

gcc -shared -pthread -fPIC -fwrapv -O2 -Wall -fno-strict-aliasing -I/usr/include/python2.7 -o analysis.so analysis.c

rm -f analysis.pyo analysis.pyc

cd -
