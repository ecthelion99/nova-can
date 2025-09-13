#!/bin/bash

# Check if the 'vcan' module is loaded
if ! lsmod | grep -q vcan; then
    echo "Loading vcan module..."
    sudo modprobe vcan
fi

# Create the vcan interface can0
echo "Creating vcan interface can0..."
sudo ip link add dev can0 type vcan

# Bring the interface up
echo "Bringing can0 interface up..."
sudo ip link set can0 up

# Confirm that the interface is up
echo "vcan interface can0 is up:"
ip link show can0
