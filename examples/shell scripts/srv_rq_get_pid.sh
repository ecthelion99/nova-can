#!/bin/bash

# Check if NODE_ID is set
if [ -z "$NODE_ID" ]; then
    echo "Error: NODE_ID environment variable is not set"
    exit 1
fi

# Check if correct number of arguments
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <destination_node_id> <constant>"
    echo "Constants:"
    echo "  0 - P"
    echo "  1 - I"
    echo "  2 - D"
    exit 1
fi

DEST_NODE_ID=$1
CONSTANT=$2

# Port ID for motor driver command message
PORT_ID=33

# Create CAN ID (assuming standard format)
# Format: priority(3) | service(1) | service_request(1) | port_id(9) | dest_id(6) | source_id(6)
CAN_ID=$(( (0 << 26 ) | (1 << 25 ) | (1 << 24 ) | (PORT_ID << 14 ) | (DEST_NODE_ID << 7 ) | NODE_ID ))

# Create the CAN frame
# Format: constant (2 bits)
DATA=$(printf "%02x" $CONSTANT)

# Send the CAN message
cansend can0 $(printf "%08x" $CAN_ID)#$DATA