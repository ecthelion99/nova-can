# Nova-CAN Examples

This directory contains examples demonstrating how to use Nova-CAN through the code generation workflow. Each example shows different aspects of the protocol and provides working code that you can use as a starting point for your own implementations.

## Overview

The examples demonstrate:
- **Basic Mock Motor Driver**: Simple motor controller implementation for Linux testing and learning
- **Code Generation Workflow**: How to use NCC to generate device-specific C code
- **System Configuration**: How to define CAN bus networks and device topologies
- **Build System Integration**: Makefile-based build process with automatic code generation
- **Testing Tools**: Scripts for sending messages and testing services

## Directory Structure

```
examples/
├── README.md                 # This file
├── Makefile                  # Build system for all examples
├── system_example.yaml       # System definition example
├── motor_driver_mock.c       # Basic mock motor driver implementation
├── dsdl/                     # Data Structure Definition Language files
│   └── nova/
│       └── motor_driver/
│           ├── msg/
│           │   └── Command.1.0.dsdl
│           └── srv/
│               ├── GetPIDConstant.1.0.dsdl
│               └── SetPIDConstant.1.0.dsdl
├── build/                    # Generated files (created during build)
└── scripts/                  # Testing and utility scripts
    ├── msg_send_command.sh
    ├── srv_rq_get_pid.sh
    └── srv_rq_set_pid.sh
```

## Motor Driver Example

The motor driver example demonstrates a **basic mock implementation** designed for learning and testing purposes. It shows:

- **Message Reception**: Receiving motor commands (current, velocity, position control)
- **Service Provision**: PID constant configuration (get/set)
- **Code Generation Integration**: How NCC generates device-specific functions
- **Callback Implementation**: Complete message and service handling
- **Linux Testing**: SocketCAN integration for development and testing

### What This Example Demonstrates

1. **Code Generation Workflow**
   - YAML device configuration → NCC → Generated C headers
   - Automatic callback function generation
   - Message and service multiplexing

2. **Message Handling**
   - Receives motor commands with different control modes
   - Processes command data and prints debug information
   - Shows how to implement auto-generated callback functions

3. **Service Implementation**
   - `GetPIDConstant`: Retrieves current PID values
   - `SetPIDConstant`: Updates PID configuration
   - Demonstrates request/response pattern (receive only)

4. **CAN Hardware Integration**
   - SocketCAN setup for Linux testing
   - Hardware filtering configuration
   - Frame reception and processing

### Important Notes

- **This is a mock implementation**: Designed for learning, not production use
- **Receive-only**: Demonstrates message reception and service requests
- **Debug output**: Prints received data for understanding
- **Linux-focused**: Uses SocketCAN for easy testing

## Code Generation Workflow

### 1. Device Configuration

The example uses `spec/interfaces/motor_driver.yaml`:

```yaml
name: MotorDriver
version: 0.1.0
messages:
  transmit:
    - name: Current
      port_type: nova.sensors.Current.1.0  
      port_id: 39
    - name: Velocity
      port_type: nova.sensors.Velocity.1.0
    - name: Position
      port_type: nova.sensors.Position.1.0
  receive:
    - name: Command
      port_type: nova.motor_driver.msg.Command.1.0
services:
  server:
    - name: SetPIDConstant
      port_type: nova.motor_driver.srv.SetPIDConstant.1.0
      port_id: 37
    - name: GetPIDConstant
      port_type: nova.motor_driver.srv.GetPIDConstant.1.0
```

### 2. Code Generation

The Makefile demonstrates the complete code generation process:

```makefile
# Generate device headers using NCC
$(MOTOR_DRIVER_H): $(DEVICE_CONFIG)
	python3 $(TOOLING_DIR)/ncc.py -d $< -o $(INCLUDE_DIR)

# Generate DSDL headers
$(DSDL_HEADERS): $(DSDL_DIR)
	nnvg --target-language c --outdir $(INCLUDE_DIR)/dsdl_headers $<
```

### 3. Generated Code

NCC generates `motor_driver.h` with:

```c
// Main receive function
int nova_can_motor_driver_rx(uint32_t *can_id, uint8_t *data, size_t* length);

// Callback functions to implement
int nova_can_motor_driver_command_callback(NOVA_CAN_CANID *can_id, 
                                          nova_motor_driver_msg_Command_1_0 *data);
int nova_can_motor_driver_set_pidconstant_callback(NOVA_CAN_CANID *can_id,
                                                   nova_motor_driver_srv_SetPIDConstant_Request_1_0 *data);
int nova_can_motor_driver_get_pidconstant_callback(NOVA_CAN_CANID *can_id,
                                                   nova_motor_driver_srv_GetPIDConstant_Request_1_0 *data);
```

### Building the Example

```bash
# Navigate to examples directory
cd examples

# Build the motor driver example
make

# The build process will:
# 1. Generate device headers from YAML configuration using NCC
# 2. Compile DSDL files to C headers using nunavut
# 3. Build the final executable with generated headers
```

### Running the Example

```bash
# Set up virtual CAN interface (Linux)
sudo ../tooling/start_vcan.sh

# Run the motor driver with node ID 1
./build/motor_driver_mock 1
```

### Testing the Example

Use the provided scripts to test different functionality:

```bash
# Send a motor command
./msg_send_command.sh 1 0 1000  # Node 1, CURRENT mode, value 1000

# Get PID constant
./srv_rq_get_pid.sh 1 0  # Node 1, P constant

# Set PID constant
./srv_rq_set_pid.sh 1 0 500  # Node 1, P constant, value 500
```

## System Configuration Example

The `system_example.yaml` file demonstrates how to define a complete CAN bus system:

```yaml
name: Drive
can_buses:
  - name: CAN1
    rate: 125000
    devices:
      - name: FLP
        node_id: 1
        device_type: motor
```

This shows:
- **System naming**: Logical system identification
- **CAN bus configuration**: Bus name and bit rate
- **Device mapping**: Node IDs and device types
- **Scalability**: Multiple buses and devices

## Data Structure Definitions (DSDL)

The `dsdl/` directory contains OpenCyphal-compatible data structure definitions:

### Message Definitions

```dsdl
# Command.1.0.dsdl
uint2 CURRENT = 0
uint2 VELOCITY = 1
uint2 POSITION = 2

uint2 mode
int16 value

@sealed
```

### Service Definitions

```dsdl
# GetPIDConstant.1.0.dsdl
uint2 P = 0
uint2 I = 1
uint2 D = 2

uint2 constant

@sealed
---

uint16 value

@sealed
```

## Build System

The `Makefile` demonstrates a complete build process with code generation:

### Key Features

1. **Code Generation**
   ```makefile
   # Generate device headers using NCC
   $(MOTOR_DRIVER_H): $(DEVICE_CONFIG)
       python3 $(TOOLING_DIR)/ncc.py -d $< -o $(INCLUDE_DIR)
   ```

2. **DSDL Compilation**
   ```makefile
   # Generate C headers from DSDL
   $(DSDL_HEADERS): $(DSDL_DIR)
       nnvg --target-language c --outdir $(INCLUDE_DIR)/dsdl_headers $<
   ```

3. **Dependency Management**
   - Automatic header generation
   - Proper dependency tracking
   - Clean build targets

### Build Targets

```bash
make          # Build all examples
make clean    # Remove generated files
make rebuild  # Clean and rebuild
```

## Testing and Validation

### Virtual CAN Setup

The `tooling/start_vcan.sh` script sets up a virtual CAN interface for testing:

```bash
#!/bin/bash
# Load CAN modules
sudo modprobe can
sudo modprobe can_raw
sudo modprobe vcan

# Create virtual interface
sudo ip link add dev can0 type vcan
sudo ip link set up can0
```

### Message Testing Scripts

1. **Command Sending** (`msg_send_command.sh`)
   - Sends motor commands to specific nodes
   - Demonstrates message construction and transmission

2. **Service Testing** (`srv_rq_get_pid.sh`, `srv_rq_set_pid.sh`)
   - Tests service request functionality
   - Shows how to construct service calls

## Learning Path

### Understanding the Code Generation

1. **Examine the YAML Configuration**
   - Look at `spec/interfaces/motor_driver.yaml`
   - Understand how messages and services are defined

2. **Study the Generated Code**
   - Check `build/include/motor_driver.h` after building
   - See how NCC transforms YAML into C functions

3. **Follow the Callback Implementation**
   - Look at `motor_driver_mock.c`
   - See how auto-generated callbacks are implemented

4. **Understand the Main Loop**
   - See how `nova_can_motor_driver_rx()` is called
   - Understand the message processing flow

### Adapting for Your Device

1. **Create Your Device Interface**
   ```yaml
   name: YourDevice
   version: 1.0.0
   messages:
     receive:
       - name: YourMessage
         port_type: your.namespace.msg.YourMessage.1.0
   ```

2. **Use Existing DSDL Types**
   - Check `examples/dsdl/` for existing message types
   - Reuse when possible to maintain compatibility

3. **Generate Your Code**
   ```bash
   python3 ../tooling/ncc/ncc.py -d your_device.yaml -o build/include
   ```

4. **Implement Your Callbacks**
   ```c
   int nova_can_yourdevice_yourmessage_callback(NOVA_CAN_CANID *can_id, 
                                                your_message_type *data) {
       // Your device-specific logic
       return 0;
   }
   ```

## Integration with Real Hardware

### Adapting the Mock for Microcontrollers

To use these examples as a starting point for real microcontrollers:

1. **Replace SocketCAN with Hardware CAN**
   ```c
   // Replace socketCAN initialization with:
   // - CAN controller configuration
   // - Hardware filter setup
   // - Interrupt handling
   ```

2. **Implement Hardware-Specific Functions**
   ```c
   // Replace read() with hardware CAN receive
   if (your_can_receive(&frame)) {
       nova_can_motor_driver_rx(&frame.id, frame.data, &frame.length);
   }
   ```

3. **Add Real Hardware Control**
   ```c
   // Replace debug prints with actual motor control
   int nova_can_motor_driver_command_callback(...) {
       // Apply motor command to hardware
       motor_set_mode(data->mode);
       motor_set_value(data->value);
       return 0;
   }
   ```

## Troubleshooting

### Common Issues

1. **Build Failures**
   - Ensure all dependencies are installed
   - Check Python path and virtual environment
   - Verify nunavut installation

2. **CAN Communication Issues**
   - Verify virtual CAN interface is running
   - Check node ID configuration
   - Ensure proper CAN frame format

3. **Code Generation Problems**
   - Validate YAML syntax
   - Check DSDL file format
   - Verify template compatibility

### Debug Tips

1. **Enable Verbose Output**
   ```bash
   make V=1  # Verbose make output
   ```

2. **Check Generated Files**
   ```bash
   ls -la build/include/  # View generated headers
   ```

3. **Monitor CAN Traffic**
   ```bash
   candump can0  # Monitor CAN messages
   ```

## Next Steps

After understanding these examples:

1. **Create Your Own Device Interface**
   - Define messages and services in YAML
   - Use existing DSDL types when possible
   - Generate device headers with NCC

2. **Implement Hardware Integration**
   - Adapt examples for your microcontroller
   - Add real hardware control logic
   - Implement error handling

3. **Build Complete Systems**
   - Define system topology
   - Configure multiple devices
   - Test end-to-end communication

## Contributing Examples

When adding new examples:

1. **Follow the Existing Structure**
   - Use the same directory layout
   - Include proper documentation
   - Add to the main Makefile

2. **Provide Complete Implementations**
   - Include all necessary files
   - Add testing scripts
   - Document hardware requirements

3. **Update This README**
   - Add example description
   - Include build instructions
   - Document any special requirements 