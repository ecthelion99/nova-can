# Nova-CAN

A lightweight, resource-efficient CAN bus communication protocol and code generation tool designed specifically for embedded systems and microcontrollers for the Monash Nova Rover team. The specification can be found

## Nova-CAN specification

The core specification is defined in LaTeX and compiled to PDF.

:page_facing_up: [View the PDF](spec/protocol/Nova-CAN-spec.pdf)

## Overview

Nova-CAN is inspired by the [OpenCyphal](https://opencyphal.org/) protocol but simplified for resource-constrained microcontrollers and the need of the team.

### Key Features

- **Device-First Design**: Define device interfaces in YAML, generate code automatically
- **Code Generation Tool (NCC)**: Transforms device configurations into ready-to-use C functions
- **Message and Service Support**: One-way messages and two-way request/response services
- **Hardware-Level CAN Filtering**: Reduces CPU load through intelligent frame filtering
- **Multi-frame Message Support**: Handles large data transfers automatically
- **OpenCyphal DSDL Compatibility**: Uses proven data structure definitions

## Architecture

### Core Components

1. **Protocol Specification** (`spec/protocol/`)
   - Complete protocol definition in LaTeX
   - CAN ID layout and message formats
   - Protocol subject definitions

2. **Code Generation Tool** (`tooling/ncc/`)
   - **NCC (Nova CAN Compiler)**: Core code generation engine
   - **YAML Configuration**: Device interface definitions
   - **Template System**: Jinja2 templates for C code generation
   - **DSDL Integration**: OpenCyphal Data Structure Description Language support

3. **Libraries** (`src/`)
   - **C Library** (`src/c/`): Core CAN ID manipulation functions
   - **Python Library** (`src/python/`): Device interface and system definition models

4. **Examples** (`examples/`)
   - Basic mock motor driver for Linux testing
   - System configuration examples
   - Build system integration

## Intended Workflow

### 1. Define Your Device Interface

Create a YAML configuration file that defines what your device can send and receive:

```yaml
# motor_driver.yaml
name: MotorDriver
version: 1.0.0
messages:
  receive:
    - name: Command
      port_type: nova.motor_driver.msg.Command.1.0
  transmit:
    - name: Status
      port_type: nova.motor_driver.msg.Status.1.0
services:
  server:
    - name: SetPIDConstant
      port_type: nova.motor_driver.srv.SetPIDConstant.1.0
```

### 2. Use Existing Message Types (or Create New Ones)

**Preferred**: Use existing DSDL message types from the `examples/dsdl/` directory:

```dsdl
# Command.1.0.dsdl
uint2 CURRENT = 0
uint2 VELOCITY = 1
uint2 POSITION = 2

uint2 mode
int16 value

@sealed
```

**If needed**: Create new message types following the OpenCyphal DSDL format.

### 3. Generate Device Code

Use the Nova CAN Compiler (NCC) to generate device-specific C headers:

```bash
# Generate device headers
python3 tooling/ncc/ncc.py -d motor_driver.yaml -o build/include

# Generate DSDL headers (if using custom types)
nnvg --target-language c --outdir build/include/dsdl_headers dsdl/nova
```

### 4. Include Generated Headers in Your Project

```c
#include "nova_can.h"
#include "motor_driver.h"  // Generated header
```

### 5. Implement Callback Functions

The generated code provides callback function signatures. Implement them to handle your device logic:

```c
// Auto-generated callback signature
int nova_can_motor_driver_command_callback(NOVA_CAN_CANID *can_id, 
                                          nova_motor_driver_msg_Command_1_0 *data) {
    // Your device-specific logic here
    switch (data->mode) {
        case nova_motor_driver_msg_Command_1_0_CURRENT:
            motor_set_current(data->value);
            break;
        case nova_motor_driver_msg_Command_1_0_VELOCITY:
            motor_set_velocity(data->value);
            break;
    }
    return 0;
}
```

### 6. Set Up CAN Hardware and Main Loop

```c
// Initialize CAN hardware
uint32_t filter, mask;
nova_can_get_canid_filter(NODE_ID, &filter);
nova_can_get_canid_mask(&mask);
// Apply filter/mask to your CAN controller

// Main processing loop
while (1) {
    // Read CAN frame from hardware
    if (can_receive(&frame)) {
        // Process with generated Nova-CAN functions
        nova_can_motor_driver_rx(&frame.id, frame.data, &frame.length);
    }
}
```

### 7. System Composition

Once you have individual devices working, you can compose them into complete systems using system composition files. These files define what devices are connected to the system:

```yaml
# system_definition.yaml
name: Rover
can_buses:
  - name: CAN1
    rate: 125000
    devices:
      - name: FrontLeftWheel
        node_id: 1
        device_type: motor_driver
      - name: FrontRightWheel
        node_id: 2
        device_type: motor_driver
  - name: CAN2
    rate: 125000
    devices:
      - name: Thermometer
        node_id: 4
        device_type: thermometer

```

System composition files serve several purposes:
- **System Documentation**: Provide a clear overview of all devices connected to each can bus
- **Bus Configuration**: Define CAN bus parameters (bit rates, etc.)
- **Tool Interpretation**: Enables tools such as nova-candump and nova-cansend (not yet implemented) to intepret the messages, and provides clear mappings for conversion to mqtt topics.

While device interfaces focus on individual device capabilities, system composition files focus on how devices work together as a complete system.

## Code Generation Tool (NCC)

The Nova CAN Compiler (NCC) is the core tool that transforms device configurations into usable C code.

### What NCC Generates

1. **Device Header File**: Contains all necessary includes and function declarations
2. **Callback Function Signatures**: Ready-to-implement function prototypes
3. **Message Multiplexing**: Automatic routing of incoming messages to correct callbacks
4. **Service Handling**: Request/response processing for services
5. **CAN ID Processing**: Automatic deserialization of CAN frames

### Generated Functions

```c
// Main receive function (call this in your main loop)
int nova_can_motor_driver_rx(uint32_t *can_id, uint8_t *data, size_t* length);

// Individual callback functions (implement these)
int nova_can_motor_driver_command_callback(NOVA_CAN_CANID *can_id, 
                                          nova_motor_driver_msg_Command_1_0 *data);
int nova_can_motor_driver_set_pidconstant_callback(NOVA_CAN_CANID *can_id,
                                                   nova_motor_driver_srv_SetPIDConstant_Request_1_0 *data);
```

### NCC Usage

```bash
python3 tooling/ncc/ncc.py -d device_config.yaml -o output_directory
```

**Arguments:**
- `-d, --device-interface`: Path to device interface YAML file
- `-o, --output-folder`: Directory to place generated files

## Current Limitations

- **Send Functions**: Message transmission is not yet implemented
- **Service Responses**: Service response sending is not yet implemented
- **Multi-frame Support**: Large message handling is planned but not implemented

## Usage with Microcontrollers

### Software Integration

1. **Include Generated Headers**
   ```c
   #include "nova_can.h"
   #include "your_device.h"  // Generated by NCC
   ```

2. **Initialize CAN Hardware**
   ```c
   // Configure your CAN controller
   // Set up hardware filters using nova_can_get_canid_filter/mask
   uint32_t filter, mask;
   nova_can_get_canid_filter(NODE_ID, &filter);
   nova_can_get_canid_mask(&mask);
   // Apply to your hardware
   ```

3. **Implement Callbacks**
   ```c
   // NCC generates these signatures - implement the logic
   int nova_can_your_device_message_callback(NOVA_CAN_CANID *can_id, 
                                             message_type *data) {
       // Your device-specific handling
       return 0;
   }
   ```

4. **Message Processing Loop**
   ```c
   while (1) {
       // Read CAN frame from your hardware
       if (your_can_receive(&frame)) {
           // Process with generated Nova-CAN function
           nova_can_your_device_rx(&frame.id, frame.data, &frame.length);
       }
   }
   ```

## Installation

### Prerequisites
- Python 3.7+
- [nunavut](https://github.com/OpenCyphal/nunavut) (for DSDL compilation)
- C compiler (GCC recommended)

### Setup
```bash
# Clone the repository
git clone <repository-url>
cd nova-can

# Install Python dependencies
pip install -r tooling/requirements.txt

# Install nunavut (for DSDL compilation)
pip install nunavut
```

## Documentation

- **Protocol Specification**: [View PDF](spec/protocol/Nova-CAN-spec.pdf) - Complete protocol details
- **Examples**: See the `examples/` directory for working implementations
- **Schema Definitions**: YAML schemas in `spec/schema/`

## Contributing

1. Follow the existing code style and structure
2. Add tests for new features
3. Update documentation for API changes
4. Ensure all examples build and run correctly

## License

[Add your license information here]

## Acknowledgments

- Inspired by the [OpenCyphal](https://opencyphal.org/) protocol
- Uses [nunavut](https://github.com/OpenCyphal/nunavut) for DSDL compilation
- Developed for the Monash Nova Rover team