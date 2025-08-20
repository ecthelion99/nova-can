#!/bin/bash

# Check if correct number of arguments
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <node_id> <value>"
    echo "Example: $0 1 1234"
    exit 1
fi

NODE_ID=$1
VALUE=$2

# Port ID for current telemetry message (from motor_driver.yaml)
PORT_ID=39

# Create CAN ID (extended format)
# Format: priority(3) | service(1) | service_request(1) | port_id(9) | dest_id(6) | source_id(6)
# Using priority 4 (Nominal), service=0, service_request=0, destination_id=0 (broadcast)
CAN_ID=$(( (4 << 26) | (0 << 25) | (0 << 24) | (PORT_ID << 14) | (0 << 7) | NODE_ID ))

# Initialize transfer ID counter
TRANSFER_ID=0

echo "Publishing current telemetry from node $NODE_ID with value $VALUE every 1 second..."
echo "CAN ID: $(printf "%08x" $CAN_ID)"
echo "Press Ctrl+C to stop"

# Loop to send message every 1 second
while true; do
    # Frame header: start_of_transfer(1) | end_of_transfer(1) | transfer_id(6)
    # For single frame: start_of_transfer=1, end_of_transfer=1
    FRAME_HEADER=$(( (1 << 7) | (1 << 6) | TRANSFER_ID ))
    
    # Convert value to little endian 16-bit integer
    # Extract low and high bytes
    LOW_BYTE=$((VALUE & 0xFF))
    HIGH_BYTE=$(( (VALUE >> 8) & 0xFF ))

    # Create data payload: frame_header + value (little endian)
    DATA=$(printf "%02x%02x%02x" $FRAME_HEADER $LOW_BYTE $HIGH_BYTE)
    
    echo "Sending message with transfer ID: $TRANSFER_ID, Data: $DATA"
    cansend can0 $(printf "%08x" $CAN_ID)#$DATA
    
    # Increment transfer ID (6-bit field, wraps around at 63)
    TRANSFER_ID=$(( (TRANSFER_ID + 1) & 0x3F ))
    
    sleep 1
done 