#!/bin/bash

R -q -e "x <- read.csv('$1', nrows=$2, header = F); summary(x); sd(x[ , 1])"
