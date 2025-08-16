#!/bin/bash

# Check if the 'vcan' module is loaded
if ! lsmod | grep -q vcan; then
    echo "Loading vcan module..."
    sudo modprobe vcan
fi

# Create the vcan interface can1
echo "Creating vcan interface can1..."
sudo ip link add dev can1 type vcan

# Bring the interface up
echo "Bringing can1 interface up..."
sudo ip link set can1 up

# Confirm that the interface is up
echo "vcan interface can1 is up:"
ip link show can1
