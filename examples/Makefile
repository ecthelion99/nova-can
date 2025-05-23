CC = gcc
WERROR_EXCEPTIONS = 
CFLAGS = -Wall -Werror $(WERROR_EXCEPTIONS)

# Directories
BUILD_DIR = build
INCLUDE_DIR = $(BUILD_DIR)/include
TOOLING_DIR = ../tooling/ncc
DSDL_DIR = dsdl/nova
# Config Files
DEVICE_CONFIG = ../spec/interfaces/motor_driver.yaml

# Source files
SRC = motor_driver_mock.c
TARGET = motor_driver_mock

# Generated files/folders
MOTOR_DRIVER_H = $(INCLUDE_DIR)/motor_driver.h
NOVA_CAN_H = $(INCLUDE_DIR)/nova_can.h
DSDL_HEADERS = $(INCLUDE_DIR)/dsdl_headers


# Default target
all: $(BUILD_DIR)/$(TARGET)

# Create build directory and include subdirectory
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)
	mkdir -p $(INCLUDE_DIR)

# Generate device header using ncc.py
$(MOTOR_DRIVER_H): $(DEVICE_CONFIG) | $(BUILD_DIR)
	python3 $(TOOLING_DIR)/ncc.py -d $< -o $(INCLUDE_DIR)

# Generate DSDL headers
$(DSDL_HEADERS): $(DSDL_DIR) | $(BUILD_DIR)
	nnvg --target-language c --outdir $(INCLUDE_DIR)/dsdl_headers $<

# Build the example program
$(BUILD_DIR)/$(TARGET): $(SRC) $(MOTOR_DRIVER_H) $(DSDL_HEADERS)
	$(CC) $(CFLAGS) -I$(INCLUDE_DIR) -I$(DSDL_HEADERS) $< -o $@

# Clean build artifacts
clean:
	rm -rf $(BUILD_DIR)

.PHONY: all clean 