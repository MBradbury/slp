#!/bin/bash

head -n $2 $1 | awk '{ total += $1; count++ } END { print total/count }'

