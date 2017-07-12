#!/bin/bash

./scripts/clean-algorithms.sh

pylint algorithm/ > algorithm.lint
pylint simulator/ > simulator.lint
pylint data/ > data.lint
