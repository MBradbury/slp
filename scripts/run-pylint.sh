#!/bin/bash

./scripts/clean-algorithms.sh

python -m pylint --version

python -m pylint algorithm/ > algorithm.lint
python -m pylint simulator/ > simulator.lint
python -m pylint data/ > data.lint
