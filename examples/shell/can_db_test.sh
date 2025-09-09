#!/bin/bash

# Function to show help
show_help() {
    echo "Usage: $0 [sleep_time]"
    echo
    echo "Optional arguments:"
    echo "  -help        Show this help message and exit"
    echo "  sleep_time   Number of seconds to wait between updates (default: 1)"
}

# Check for help flag
if [ "$1" == "-help" ] || [ "$1" == "--help" ]; then
    show_help
    exit 0
fi

# Default sleep time (in seconds)
SLEEP_TIME=0.05

# If a command-line argument is provided, use it as sleep time
# -z tests if the string is emply
# so if arguement is not empty, use it
if [ ! -z "$1" ]; then
    SLEEP_TIME=$1
fi

# Port IDs for telemetry types
PORT_IDS=(39 40 41)

# Initialize transfer ID counter
TRANSFER_ID=0

# Start at 0
VALUE=0

echo "Publishing Current, Velocity, and Position for nodes 1–8, cycling value 0 → 20 → 0 every second..."
echo "Press Ctrl+C to stop"

while true; do
    PORT_NAMES=("Current" "Velocity" "Position")
    for NODE_ID in {1..8}; do
        for i in "${!PORT_IDS[@]}"; do
            PORT_ID=${PORT_IDS[$i]}
            TYPE_NAME=${PORT_NAMES[$i]}

            # Create CAN ID (extended format)
            CAN_ID=$(( (4 << 26) | (0 << 25) | (0 << 24) | (PORT_ID << 14) | (0 << 7) | NODE_ID ))

            # Frame header: start_of_transfer=1, end_of_transfer=1, transfer_id
            FRAME_HEADER=$(( (1 << 7) | (1 << 6) | TRANSFER_ID ))

            # Convert value to little endian 16-bit integer
            LOW_BYTE=$((VALUE & 0xFF))
            HIGH_BYTE=$(( (VALUE >> 8) & 0xFF ))

            # Create data payload: frame_header + value (little endian)
            DATA=$(printf "%02x%02x%02x" $FRAME_HEADER $LOW_BYTE $HIGH_BYTE)

            echo "Node $NODE_ID [$TYPE_NAME] → Value $VALUE, Transfer ID $TRANSFER_ID, CAN ID: $(printf "%08x" $CAN_ID), Data: $DATA"
            cansend can1 $(printf "%08x" $CAN_ID)#$DATA
        done
    done

    PORT_NAMES=("Current" "Voltage" "MaxVoltage")

    for NODE_ID in {9..10}; do
        for i in "${!PORT_IDS[@]}"; do
            PORT_ID=${PORT_IDS[$i]}
            TYPE_NAME=${PORT_NAMES[$i]}

            # Create CAN ID (extended format)
            CAN_ID=$(( (4 << 26) | (0 << 25) | (0 << 24) | (PORT_ID << 14) | (0 << 7) | NODE_ID ))

            # Frame header: start_of_transfer=1, end_of_transfer=1, transfer_id
            FRAME_HEADER=$(( (1 << 7) | (1 << 6) | TRANSFER_ID ))

            # Convert value to little endian 16-bit integer
            LOW_BYTE=$((VALUE & 0xFF))
            HIGH_BYTE=$(( (VALUE >> 8) & 0xFF ))

            # Create data payload: frame_header + value (little endian)
            DATA=$(printf "%02x%02x%02x" $FRAME_HEADER $LOW_BYTE $HIGH_BYTE)

            echo "Node $NODE_ID [$TYPE_NAME] → Value $VALUE, Transfer ID $TRANSFER_ID, CAN ID: $(printf "%08x" $CAN_ID), Data: $DATA"
            cansend can1 $(printf "%08x" $CAN_ID)#$DATA
        done
    done

    # Increment value and wrap at 21
    VALUE=$((VALUE + 1))
    if [ "$VALUE" -gt 20 ]; then
        VALUE=0
    fi

    # Increment transfer ID (6-bit, wraps at 63)
    TRANSFER_ID=$(( (TRANSFER_ID + 1) & 0x3F ))

    sleep $SLEEP_TIME
done
