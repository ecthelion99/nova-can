#!/bin/bash

# Check if NODE_ID is set
if [ -z "$NODE_ID" ]; then
    echo "Error: NODE_ID environment variable is not set"
    exit 1
fi

# Check if correct number of arguments
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <destination_node_id> <port_id> <value>"
    echo "port_id's:"
    echo "  33 - CURRENT"
    echo "  34 - VELOCITY"
    echo "  35 - POSITION"
    exit 1
fi

DEST_NODE_ID=$1
PORT_ID=$2
VALUE=$3

# Create CAN ID (assuming standard format)
# Format: priority(3) | service(1) | service_request(1) | port_id(9) | dest_id(6) | source_id(6)
CAN_ID=$(( (0 << 26 ) | (0 << 25 ) | (0 << 24 ) | (PORT_ID << 14 ) | (DEST_NODE_ID << 7 ) | NODE_ID ))

FIRST_BYTE=0x00
SECOND_BYTE=$(($VALUE & 0xFF))
THIRD_BYTE=$((($VALUE >> 8) & 0xFF))
DATA=$(printf "%02x%02x%02x" $FIRST_BYTE $SECOND_BYTE $THIRD_BYTE)


# Send the CAN message
cansend can0 $(printf "%08x" $CAN_ID)#$DATA 