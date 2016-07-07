#!/bin/bash

MAIN_IHEX=$1
NODEID=$2

NEW_MAIN_IHEX="$MAIN_IHEX-$NODEID"

AMADDR=ActiveMessageAddressC__addr

echo "Setting TOS_NODE_ID and $AMADDR to $NODEID in $MAIN_IHEX to $NEW_MAIN_IHEX"

tos-set-symbols --objcopy msp430-objcopy --objdump msp430-objdump --target ihex $MAIN_IHEX $NEW_MAIN_IHEX TOS_NODE_ID=$NODEID $AMADDR=$NODEID

echo "Flashing mote with the image $NEW_MAIN_IHEX"

tos-bsl --telosb -c /dev/ttyUSB0 -r -e -I -p $NEW_MAIN_IHEX
