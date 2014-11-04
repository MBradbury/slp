#!/bin/bash
ps aux | grep python | tr -s ' ' | cut -d ' ' -f 2 | xargs kill -9
